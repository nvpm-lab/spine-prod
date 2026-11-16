"""ProtoDUNE-SP released bundles and track-aware recombination contracts."""

import copy
from pathlib import Path

import pytest

from src.config_manager import ConfigManager
from tests.config_migration import fingerprint

spine_config = pytest.importorskip("spine.config")
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
PDSP = "infer/protodune-sp"

MC_GAIN = 984.6396218983853
DATA_GAIN = 963.3911368015414


@pytest.fixture(autouse=True)
def config_environment(monkeypatch):
    monkeypatch.setenv("SPINE_CONFIG_PATH", str(CONFIG))
    monkeypatch.setenv("SPINE_PROD_BASEDIR", str(ROOT))


def load(path):
    return spine_config.load_config_file(str(CONFIG / path), download=False)


def compose(*paths):
    text = "include:\n" + "".join(f"  - {path}\n" for path in paths)
    return spine_config.load_config(text, root_dir=str(CONFIG), download=False)


def comparable(config):
    """Replace unresolved download tags, which compare by identity."""
    config = copy.deepcopy(config)
    config["model"]["weight_path"] = vars(config["model"]["weight_path"])
    return config


def stage(config, name):
    return next(s for s in config["post"]["stages"] if s["name"] == name)


def without_stage(config, name):
    return [s for s in config["post"]["stages"] if s["name"] != name]


def by_name(stages):
    return {s["name"]: {k: v for k, v in s.items() if k != "name"} for s in stages}


@pytest.mark.parametrize(
    "paths,expected",
    [
        (
            ("full_chain_260210.yaml",),
            "09cf4a2a8fa63ac396e8671e725058d599f2c9b7beff06636e7fc639b754a35c",
        ),
        (
            ("full_chain_260906.yaml",),
            "ba38c1ad8d0ed95aaf3a92f5172453c44e923b5c6ea9381f296089a71b933f4e",
        ),
        (
            ("full_chain_260210.yaml", "modifier/data/mod_data_260210.yaml"),
            "19b681cf939970b253e6765de1c53f30228bbd89f660b102900ea049138ee9ab",
        ),
        (
            ("full_chain_260906.yaml", "modifier/data/mod_data_260906.yaml"),
            "3c1c0e3dbd5f94691b4855ce855e63d003cc8cdfcf77aaa8aee81e8ed215c056",
        ),
    ],
    ids=lambda value: "+".join(value) if isinstance(value, tuple) else None,
)
def test_released_bundles_are_unchanged(paths, expected):
    config = compose(*(f"{PDSP}/{path}" for path in paths))
    assert fingerprint(config, CONFIG) == expected


def test_261116_only_adds_post_calibration_before_calo_ke():
    old = comparable(load(f"{PDSP}/full_chain_260906.yaml"))
    new = comparable(load(f"{PDSP}/full_chain_261116.yaml"))

    assert {k: v for k, v in new.items() if k != "post"} == {
        k: v for k, v in old.items() if k != "post"
    }
    names = [s["name"] for s in new["post"]["stages"]]
    assert names.index("calibration") == names.index("calo_ke") - 1
    assert without_stage(new, "calibration") == old["post"]["stages"]


def test_261116_post_calibration_matches_in_chain_calibration():
    config = load(f"{PDSP}/full_chain_261116.yaml")
    calibration = stage(config, "calibration")
    assert calibration["depositions_source"] == "depositions_q"
    assert calibration["do_tracking"] is True

    # Lifetime must be corrected before the inverse Box sees the local dQ/dx
    post = calibration["stages"]
    assert [s["name"] for s in post] == ["gain", "lifetime", "recombination"]

    in_chain = by_name(config["model"]["modules"]["calibration"]["stages"])
    post = by_name(post)
    assert post["gain"] == in_chain["gain"] == {"gain": MC_GAIN}
    assert post["lifetime"] == in_chain["lifetime"]
    recombination = dict(post["recombination"])
    tracking = {k: recombination.pop(k) for k in list(recombination)
                if k in ("tracking_mode", "segment_length", "min_count")}
    assert recombination == in_chain["recombination"]
    assert tracking["tracking_mode"] == "bin_pca"
    assert tracking["segment_length"] > 0 and tracking["min_count"] > 0


def test_261116_data_modifier_uses_data_gain_everywhere():
    mc = load(f"{PDSP}/full_chain_261116.yaml")
    data = compose(
        f"{PDSP}/full_chain_261116.yaml", f"{PDSP}/modifier/data/mod_data_261116.yaml"
    )
    model_gain = by_name(data["model"]["modules"]["calibration"]["stages"])["gain"]
    post = stage(data, "calibration")
    assert model_gain == by_name(post["stages"])["gain"] == {"gain": DATA_GAIN}

    # Apart from the gain, the data post calibration is the MC one
    mc_stages = copy.deepcopy(stage(mc, "calibration"))
    mc_stages["stages"][0]["gain"] = DATA_GAIN
    assert post == mc_stages

    # Everything else matches the released 260906 data composite
    old = comparable(
        compose(
            f"{PDSP}/full_chain_260906.yaml",
            f"{PDSP}/modifier/data/mod_data_260906.yaml",
        )
    )
    data = comparable(data)
    assert without_stage(data, "calibration") == old["post"]["stages"]
    assert {k: v for k, v in data.items() if k != "post"} == {
        k: v for k, v in old.items() if k != "post"
    }


def test_261116_data_modifier_rejects_bundles_without_post_calibration():
    with pytest.raises(spine_config.errors.ConfigPathError):
        compose(
            f"{PDSP}/full_chain_260906.yaml",
            f"{PDSP}/modifier/data/mod_data_261116.yaml",
        )


@pytest.mark.parametrize(
    "bundle,expected",
    [
        ("full_chain_260210.yaml", "mod_data_260210.yaml"),
        ("full_chain_260906.yaml", "mod_data_260906.yaml"),
        ("full_chain_261116.yaml", "mod_data_261116.yaml"),
    ],
)
def test_data_modifier_resolution_follows_bundle_version(bundle, expected):
    manager = ConfigManager(ROOT)
    path = CONFIG / PDSP / bundle
    selected = manager.resolve_modifier_version(
        "data",
        manager.discover_modifiers(str(path))["data"],
        manager.extract_version(path),
        None,
    )
    assert selected.name == expected


def test_261116_post_calibration_builds_ordered_tracking_calibrator():
    pytest.importorskip("spine.post")
    from spine.geo import GeoManager
    from spine.post.manager import PostManager

    config = load(f"{PDSP}/full_chain_261116.yaml")
    GeoManager.reset()
    try:
        GeoManager.initialize_or_get(**config["geo"])
        manager = PostManager({"stages": [stage(config, "calibration")]})
        (processor,) = manager.modules.values()
        assert processor.do_tracking is True
        assert processor.depositions_source == "depositions_q"
        calibrator = processor.calibrator
        assert list(calibrator.module_names.values()) == [
            "gain",
            "lifetime",
            "recombination",
        ]
        recombination = next(
            module
            for key, module in calibrator.modules.items()
            if calibrator.module_names[key] == "recombination"
        )
        settings = by_name(stage(config, "calibration")["stages"])["recombination"]
        assert recombination.tracking_mode == "bin_pca"
        assert recombination.tracking_kwargs == {
            "segment_length": settings["segment_length"],
            "min_count": settings["min_count"],
        }
    finally:
        GeoManager.reset()
