from app.services import brand_profile_service as service


def test_brand_profile_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "PROFILE_DIR", tmp_path)
    created = service.create_brand_profile(
        {
            "brand_name": "Test Brand",
            "industry": "Technology",
            "target_audience": "Developers",
            "keywords": "ai, tools",
        }
    )
    assert created.id
    assert service.load_brand_profile(created.id).brand_name == "Test Brand"
    updated = service.update_brand_profile(created.id, {"tone": "Friendly"})
    assert updated.tone == "Friendly"
    assert service.delete_brand_profile(created.id)
