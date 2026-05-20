"""Firebase sign-in helper.

Opens a browser window → you sign in with email/password → FIREBASE_REFRESH_TOKEN
and FIREBASE_UID are written to .env automatically.

Usage:
    python scripts/login.py
"""

from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import threading
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / ".env"

load_dotenv(ENV_FILE)

_FIREBASE_API_KEY = os.environ["FIREBASE_API_KEY"]
_FIREBASE_PROJECT_ID = os.environ["FIREBASE_PROJECT_ID"]

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>FFE Tool — Sign in</title>
  <style>
    body   {{ font-family: sans-serif; max-width: 380px; margin: 80px auto; padding: 24px; text-align: center; }}
    h2     {{ margin-bottom: 32px; }}
    button {{ padding: 12px 24px; background: #4285f4; color: #fff; border: none;
              border-radius: 4px; font-size: 15px; cursor: pointer; display: inline-flex;
              align-items: center; gap: 10px; }}
    button:hover {{ background: #2a6fde; }}
    #status {{ margin-top: 24px; font-size: 14px; }}
    .error   {{ color: #c62828; }}
    .success {{ color: #2e7d32; font-weight: bold; }}
  </style>
</head>
<body>
  <h2>FFE Tool — Sign in</h2>
  <button onclick="signIn()">
    <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFF" d="M44.5 20H24v8.5h11.8C34.7 33.9 30.1 37 24 37c-7.2 0-13-5.8-13-13s5.8-13 13-13c3.1 0 5.9 1.1 8.1 2.9l6.4-6.4C34.6 4.1 29.6 2 24 2 11.8 2 2 11.8 2 24s9.8 22 22 22c11 0 21-8 21-22 0-1.3-.2-2.7-.5-4z"/></svg>
    Sign in with Google
  </button>
  <div id="status"></div>

  <script type="module">
    import {{ initializeApp }}        from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js';
    import {{ getAuth, signInWithPopup, GoogleAuthProvider }}
                                      from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js';

    const app  = initializeApp({{ apiKey: '{api_key}', authDomain: '{auth_domain}' }});
    const auth = getAuth(app);

    window.signIn = async function() {{
      const status = document.getElementById('status');
      status.textContent = 'Opening Google sign-in\u2026';
      status.className   = '';
      try {{
        const result = await signInWithPopup(auth, new GoogleAuthProvider());
        const user   = result.user;
        await fetch('/callback', {{
          method:  'POST',
          headers: {{'Content-Type': 'application/json'}},
          body:    JSON.stringify({{ refreshToken: user.refreshToken, uid: user.uid }}),
        }});
        status.textContent = '\u2713 Signed in! You can close this tab.';
        status.className   = 'success';
      }} catch (e) {{
        status.textContent = 'Error: ' + e.message;
        status.className   = 'error';
      }}
    }};
  </script>
</body>
</html>
"""

_result: dict[str, str] | None = None
_server_ref: socketserver.TCPServer | None = None


def _upsert_env(key: str, value: str) -> None:
    """Set or replace KEY=value in .env, appending if the key is absent."""
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(f"{key}={value}", text)
    else:
        text = text.rstrip("\n") + f"\n{key}={value}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A002
        pass  # suppress request noise

    def do_GET(self) -> None:  # noqa: N802
        html = _HTML.format(
            api_key=_FIREBASE_API_KEY,
            auth_domain=f"{_FIREBASE_PROJECT_ID}.firebaseapp.com",
        )
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        global _result
        length = int(self.headers.get("Content-Length", 0))
        _result = json.loads(self.rfile.read(length))
        self.send_response(204)
        self.end_headers()
        # Shut down the server without deadlocking the request thread
        threading.Thread(target=_server_ref.shutdown, daemon=True).start()  # type: ignore[union-attr]


def main() -> None:
    global _server_ref

    with socketserver.TCPServer(("localhost", 0), _Handler) as server:
        _server_ref = server
        port = server.server_address[1]
        url = f"http://localhost:{port}"
        print(f"Opening {url} …")
        webbrowser.open(url)
        server.serve_forever()

    if _result:
        _upsert_env("FIREBASE_REFRESH_TOKEN", _result["refreshToken"])
        _upsert_env("FIREBASE_UID", _result["uid"])
        print(f"✓ .env updated  (UID: {_result['uid']})")
    else:
        print("✗ Sign-in was not completed.")


if __name__ == "__main__":
    main()
