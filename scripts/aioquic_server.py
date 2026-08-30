"""Minimal HTTP/3 static file server on aioquic, a second, independent QUIC stack for the
W4 replication (Caddy uses quic-go; this uses aioquic). Serves a www directory over h3 so
the same Chromium cold-load harness can measure request concurrency against a different
server implementation. If the peak concurrency is still ~6, the under-multiplexing is the
client's QUIC scheduler, not a quic-go/Caddy property.

Usage: python3 aioquic_server.py --www DIR --port 8444 --cert cert.pem --key key.pem
"""
import argparse
import asyncio
import mimetypes
import os

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import HeadersReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ProtocolNegotiated

WWW = None


class H3Static(QuicConnectionProtocol):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._http = None

    def quic_event_received(self, event):
        if isinstance(event, ProtocolNegotiated):
            self._http = H3Connection(self._quic)
        if self._http is not None:
            for e in self._http.handle_event(event):
                if isinstance(e, HeadersReceived):
                    self._serve(e)

    def _serve(self, e):
        headers = dict(e.headers)
        path = headers.get(b":path", b"/").decode().split("?")[0]
        if path == "/":
            path = "/index.html"
        fp = os.path.normpath(os.path.join(WWW, path.lstrip("/")))
        if not fp.startswith(WWW) or not os.path.isfile(fp):
            self._http.send_headers(e.stream_id, [(b":status", b"404")], end_stream=True)
            self.transmit()
            return
        ctype = (mimetypes.guess_type(fp)[0] or "application/octet-stream").encode()
        body = open(fp, "rb").read()
        self._http.send_headers(e.stream_id, [
            (b":status", b"200"), (b"content-type", ctype),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store")])
        self._http.send_data(e.stream_id, body, end_stream=True)
        self.transmit()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--www", required=True)
    ap.add_argument("--port", type=int, default=8444)
    ap.add_argument("--cert", required=True)
    ap.add_argument("--key", required=True)
    args = ap.parse_args()
    global WWW
    WWW = os.path.abspath(args.www)
    cfg = QuicConfiguration(is_client=False, alpn_protocols=["h3"], max_datagram_frame_size=65536)
    cfg.load_cert_chain(args.cert, args.key)
    print(f"[aioquic] serving {WWW} on :{args.port} (h3)", flush=True)
    await serve("0.0.0.0", args.port, configuration=cfg, create_protocol=H3Static)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
