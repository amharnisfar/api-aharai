from flask import Flask, request, Response, send_file
import requests
import re

app = Flask(__name__)

TARGET = "https://owner-adjust-characters-channels.trycloudflare.com"


# Serve local favicon
@app.route("/bhi.png")
def favicon():
    return send_file("bhi.png", mimetype="image/png")


# Catch ALL routes (/, /login, /admin, /admin/grade@11, etc.)
@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy(path):
    target_url = f"{TARGET}/{path}"

    # Forward request to target
    resp = requests.request(
        method=request.method,
        url=target_url,
        headers={k: v for k, v in request.headers if k.lower() != "host"},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False
    )

    # ----- FIX REDIRECTS & COOKIES -----
    headers = []
    for name, value in resp.headers.items():
        lname = name.lower()

        # Rewrite redirect Location
        if lname == "location":
            if value.startswith(TARGET):
                value = value.replace(TARGET, "")
            headers.append((name, value))
            continue

        # Rewrite cookie domain
        if lname == "set-cookie":
            value = re.sub(r"Domain=[^;]+;?", "", value, flags=re.IGNORECASE)
            headers.append((name, value))
            continue

        if lname not in (
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection",
        ):
            headers.append((name, value))

    content = resp.content
    content_type = resp.headers.get("content-type", "")

    # ----- HTML REWRITING -----
    if "text/html" in content_type:
        html = content.decode("utf-8", errors="ignore")

        # Remove absolute target URLs everywhere
        html = html.replace(TARGET, "")

        # Fix assets (CSS / JS / images)
        html = re.sub(r'href="/', f'href="{TARGET}/', html)
        html = re.sub(r'src="/', f'src="{TARGET}/', html)

        # Force title
        html = re.sub(
            r"<title>.*?</title>",
            "<title>Baithul Hamdu Institute</title>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Remove existing favicons
        html = re.sub(
            r'<link[^>]+rel=["\'].*icon.*["\'][^>]*>',
            "",
            html,
            flags=re.IGNORECASE,
        )

        # Inject favicon + HARD navigation guard (NO f-string)
        inject = """
<link rel="icon" type="image/png" href="/bhi.png">
<script>
(function () {
  const TARGET = "__TARGET__";

  // Intercept anchor clicks
  document.addEventListener("click", function(e) {
    const a = e.target.closest("a");
    if (!a || !a.href) return;
    if (a.href.startsWith(TARGET)) {
      e.preventDefault();
      location.href = a.href.replace(TARGET, "");
    }
  });

  // Override JS redirects
  ["assign","replace"].forEach(function(fn) {
    const orig = location[fn];
    location[fn] = function(url) {
      if (typeof url === "string" && url.startsWith(TARGET)) {
        return orig.call(location, url.replace(TARGET, ""));
      }
      return orig.call(location, url);
    };
  });
})();
</script>
"""
        inject = inject.replace("__TARGET__", TARGET)
        html = html.replace("<head>", "<head>" + inject)

        content = html.encode("utf-8")

    return Response(content, resp.status_code, headers)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
