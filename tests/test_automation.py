import json, time
import pytest
from engineering_os.automation import Automation, Workflow, ConnectorInput


def definition(**kwargs):
    return Workflow(
        name="Intake",
        steps=[
            {
                "id": "brief",
                "kind": "transform",
                "name": "Prepare",
                "template": "Hello ${name}",
            },
            {"id": "review", "kind": "approval", "name": "Review"},
            {"id": "outcome", "kind": "record", "name": "Save", "template": "${brief}"},
        ],
        **kwargs,
    )


def test_real_workflow_approval_and_evidence(store):
    a = Automation(store)
    wid = a.workflow(definition())
    rid = a.queue(wid, {"name": "Morgan"})
    a.execute(rid)
    run = a.snapshot()["runs"][0]
    assert run["status"] == "waiting_approval" and run["cursor"] == 1
    assert run["context"]["brief"] == "Hello Morgan"
    a.decide(rid, True, "Reviewed the brief")
    run = a.snapshot()["runs"][0]
    assert run["status"] == "completed" and run["context"]["outcome"] == "Hello Morgan"
    assert [e["kind"] for e in a.snapshot()["evidence"]].count("step_completed") == 3


def test_ai_needs_approval_and_missing_configuration_blocks(store, monkeypatch):
    monkeypatch.delenv("HIYO_AI_API_KEY", raising=False)
    monkeypatch.setenv("HIYO_AI_PROVIDER", "openai")
    a = Automation(store)
    w = Workflow(
        name="AI",
        steps=[
            {"id": "ai", "kind": "ai", "name": "Draft", "template": "Prepare a summary"}
        ],
    )
    rid = a.queue(a.workflow(w), {})
    a.execute(rid)
    assert a.snapshot()["runs"][0]["status"] == "waiting_approval"
    a.decide(rid, True, "Approve this AI call")
    r = a.snapshot()["runs"][0]
    assert r["status"] == "blocked" and "not configured" in r["error"]
    assert r["approved"] == []


def test_mocked_ai_usage_is_evidence_not_invented_provider_result(store, monkeypatch):
    monkeypatch.setenv("HIYO_AI_PROVIDER", "openai")
    a = Automation(store)
    monkeypatch.setattr(
        a,
        "ai",
        lambda prompt: (
            "Fixture AI response",
            {"input_tokens": 2, "output_tokens": 3, "fixture": True},
        ),
    )
    rid = a.queue(
        a.workflow(
            Workflow(
                name="Draft",
                steps=[
                    {"id": "draft", "kind": "ai", "name": "AI", "template": "Summarize"}
                ],
            )
        ),
        {},
    )
    a.execute(rid)
    a.decide(rid, True, "Fixture usage")
    r = a.snapshot()["runs"][0]
    assert r["status"] == "completed" and r["context"]["draft"] == "Fixture AI response"


def test_scheduling_prevents_duplicate_pending_work_and_stop(store):
    a = Automation(store)
    a.workflow(definition(trigger="schedule", interval_seconds=60))
    assert len(a.tick(time.time() + 61)) == 1
    assert a.tick(time.time() + 121) == []
    a.stop()
    assert a.tick(time.time() + 181) == []
    with pytest.raises(ValueError, match="stop"):
        a.queue(a.snapshot()["workflows"][0]["id"], {})


def test_connector_destination_and_credential_scope_validation(store):
    a = Automation(store)
    for url in [
        "http://api.example.com",
        "https://127.0.0.1",
        "https://169.254.169.254",
        "https://user:password@api.example.com",
    ]:
        with pytest.raises(ValueError):
            a.connector(ConnectorInput(name="Unsafe", base_url=url, auth="none"))
    with pytest.raises(ValueError):
        ConnectorInput(
            name="Unsafe",
            base_url="https://api.example.com",
            credential_variable="PATH",
        )
    cid = a.connector(
        ConnectorInput(
            name="HubSpot",
            base_url="https://api.hubapi.com",
            credential_variable="HIYO_CONNECTOR_HUBSPOT",
        )
    )
    c = next(c for c in a.snapshot()["connectors"] if c["id"] == cid)
    assert c["status"] == "needs_configuration" and not c["credential_present"]


def test_connector_has_approval_and_allowlist_gate(store, monkeypatch):
    a = Automation(store)
    cid = a.connector(
        ConnectorInput(name="Example", base_url="https://api.example.com", auth="none")
    )
    rid = a.queue(
        a.workflow(
            Workflow(
                name="Fetch",
                steps=[
                    {
                        "id": "get",
                        "kind": "connector",
                        "name": "Fetch records",
                        "connector_id": cid,
                        "method": "GET",
                        "path": "/records",
                    }
                ],
            )
        ),
        {},
    )
    a.execute(rid)
    assert a.snapshot()["runs"][0]["status"] == "waiting_approval"
    a.decide(rid, True, "Approve read")
    r = a.snapshot()["runs"][0]
    assert r["status"] == "blocked" and "allowlist" in r["error"]


def test_json_mapping_cannot_inject_new_fields(store, monkeypatch):
    a = Automation(store)
    monkeypatch.setenv("HIYO_CONNECTOR_HOSTS", "api.example.com")
    cid = a.connector(
        ConnectorInput(name="Test", base_url="https://api.example.com", auth="none")
    )
    captured = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, n):
            return b'{"ok":true}'

    class Opener:
        def open(self, req, timeout):
            captured.append(json.loads(req.data))
            return Response()

    monkeypatch.setattr(
        "engineering_os.automation.urllib.request.build_opener", lambda *args: Opener()
    )
    value = 'a", "admin":true, "other":"x'
    output = a.request_connector(
        {"connector_id": cid, "method": "POST", "path": "/records"},
        {"name": value},
        '{"name":"${name}"}',
    )
    assert captured == [{"name": value}] and json.loads(output) == {"ok": True}


def test_condition_does_not_continue_and_denial_cancels(store):
    a = Automation(store)
    w = Workflow(
        name="Gate",
        steps=[
            {
                "id": "check",
                "kind": "condition",
                "name": "Condition",
                "field": "state",
                "equals": "approved",
            },
            {
                "id": "output",
                "kind": "record",
                "name": "Save",
                "template": "Should not run",
            },
        ],
    )
    rid = a.queue(a.workflow(w), {"state": "pending"})
    a.execute(rid)
    assert a.snapshot()["runs"][0]["status"] == "skipped"
    rid = a.queue(a.workflow(definition()), {"name": "Morgan"})
    a.execute(rid)
    a.decide(rid, False, "Rejected")
    assert (
        next(r for r in a.snapshot()["runs"] if r["id"] == rid)["status"] == "cancelled"
    )


def test_universal_graphql_and_soap_adapters(store, monkeypatch):
    a = Automation(store)
    monkeypatch.setenv("HIYO_CONNECTOR_HOSTS", "api.example.com")
    requests = []

    class Response:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, n):
            return self.payload

    class Opener:
        def open(self, req, timeout):
            requests.append(req)
            return Response(
                b"<Envelope><Body>accepted</Body></Envelope>"
                if "soap" in req.get_header("Content-type", "")
                else b'{"data":{"ok":true}}'
            )

    monkeypatch.setattr(
        "engineering_os.automation.urllib.request.build_opener", lambda *args: Opener()
    )
    graphql = a.connector(
        ConnectorInput(
            name="GraphQL",
            base_url="https://api.example.com",
            auth="none",
            protocol="graphql",
        )
    )
    a.request_connector(
        {"connector_id": graphql, "method": "POST", "path": "/graphql"},
        {"name": "Morgan"},
        '{"query":"query Test($name: String!) { user(name:$name) { id } }","variables":{"name":"${name}"}}'.replace(
            "$name:", "$$name:"
        ).replace(
            "name:$name", "name:$$name"
        ),
    )
    assert json.loads(requests[-1].data)["variables"]["name"] == "Morgan"
    soap = a.connector(
        ConnectorInput(
            name="SOAP",
            base_url="https://api.example.com",
            auth="none",
            protocol="soap",
        )
    )
    output = a.request_connector(
        {"connector_id": soap, "method": "POST", "path": "/soap"},
        {"name": "<unsafe>"},
        "<Envelope><Body>${name}</Body></Envelope>",
    )
    assert b"&lt;unsafe&gt;" in requests[-1].data and "xml" in json.loads(output)
    with pytest.raises(ValueError, match="DTDs"):
        a.request_connector(
            {"connector_id": soap, "method": "POST", "path": "/soap"},
            {},
            '<!DOCTYPE x [<!ENTITY y SYSTEM "file:///etc/passwd">]><x>&y;</x>',
        )


def test_local_ai_has_no_cloud_fallback(store, monkeypatch):
    monkeypatch.setenv("HIYO_AI_PROVIDER", "ollama")
    a = Automation(store)
    urls = []

    class Broken:
        def open(self, req, timeout):
            urls.append(req.full_url)
            raise OSError("Local model unavailable")

    monkeypatch.setattr(
        "engineering_os.automation.urllib.request.build_opener", lambda *args: Broken()
    )
    with pytest.raises(RuntimeError, match="no paid cloud fallback"):
        a.ai("Summarize this request")
    assert urls == ["http://127.0.0.1:11434/api/generate"]


def test_template_expansion_is_bounded_before_large_allocation():
    from engineering_os.automation import bounded_template

    assert (
        bounded_template("Hello ${name}; $$5", {"name": "Morgan"}) == "Hello Morgan; $5"
    )
    with pytest.raises(ValueError, match="64 KiB"):
        bounded_template("${large}" * 1000, {"large": "x" * 4096})
