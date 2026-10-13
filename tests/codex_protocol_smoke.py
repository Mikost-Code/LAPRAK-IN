"""No browser or inference: check installed official app-server initialization."""
from laprak.codex import Server, command, safe_auth_url

with Server(timeout=15) as server:
    account = server.request("account/read", {"refreshToken": False})
    config = server.request("config/read", {"includeLayers": False})["config"]
    assert config["features"]["shell_tool"] is False
    assert config["web_search"] == "disabled"
    assert config["cli_auth_credentials_store"] == "keyring"
    print("Codex protocol OK; account present:", bool(account.get("account")))
    print("Direct native executable:", command()[0].endswith("codex.exe"))
    attempt = server.request("account/login/start", {"type": "chatgpt", "useHostedLoginSuccessPage": True, "appBrand": "codex"})
    safe_auth_url(attempt["authUrl"])
    assert attempt["loginId"]
    server.request("account/login/cancel", {"loginId": attempt["loginId"]})
    print("Official browser login initiation and cancellation OK (no browser opened).")
