def _indicator_names(client, headers, node_id):
    def find(nodes):
        for n in nodes:
            if n["id"] == node_id:
                return n
            hit = find(n["children"])
            if hit:
                return hit
    return sorted(i["indicator_name"] for i in find(client.get("/kpis/tree", headers=headers).json())["indicators"])


def test_template_lifecycle(client, admin):
    tpl = client.post("/templates", json={"name": "Line KPIs"}, headers=admin).json()["template_id"]
    add = client.post(f"/templates/{tpl}/indicators", json={"indicator_name_in_template": "Scrap", "default_calculation_type": "Incremental"}, headers=admin)
    assert add.status_code == 200
    node = client.post("/kpis/nodes", json={"name": "Line 1"}, headers=admin).json()["node_id"]

    res = client.post(f"/templates/{tpl}/apply", json={"node_id": node}, headers=admin)
    assert res.status_code == 200 and res.json()["applied"] == 1
    assert _indicator_names(client, admin, node) == ["Scrap"]

    # new definitions propagate to linked folders
    client.post(f"/templates/{tpl}/indicators", json={"indicator_name_in_template": "OEE", "default_calculation_type": "Average"}, headers=admin)
    assert _indicator_names(client, admin, node) == ["OEE", "Scrap"]

    defs = client.get(f"/templates/{tpl}/indicators", headers=admin).json()
    scrap = next(d for d in defs if d["indicator_name_in_template"] == "Scrap")
    assert scrap["default_calculation_type"] == "Sum"  # legacy alias normalized
    upd = client.put(f"/templates/indicators/{scrap['id']}", json={"template_id": tpl, "name": "Scrap Rate", "calc_type": "Average"}, headers=admin)
    assert upd.status_code == 200
    assert _indicator_names(client, admin, node) == ["OEE", "Scrap Rate"]

    assert client.delete(f"/templates/indicators/{scrap['id']}", headers=admin).status_code == 200
    assert _indicator_names(client, admin, node) == ["OEE"]

    # deleting the template keeps the KPIs it created (this used to 500)
    assert client.delete(f"/templates/{tpl}", headers=admin).status_code == 200
    assert _indicator_names(client, admin, node) == ["OEE"]
    assert client.delete(f"/templates/{tpl}", headers=admin).status_code == 404
