"""Tests for the RNDIS handover inside MirrorService.

Start/stop must not leave the always-on USB network detached: start() frees the
UDC the configfs gadget holds, stop() hands it back and re-binds DHCP.
"""

import pytest

from lib import mirror_service

# mirror_service imports the module by its flat name (the device layout puts the
# middleware directory on sys.path), so patch that module object, not the
# package-qualified one.
import gadget_linux


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Temporary framebuffer, silent serve loop, recorded shell + handover calls."""
    fb = tmp_path / 'fb.raw'
    fb.write_bytes(b'\x02' * mirror_service.FB_SIZE)
    monkeypatch.setattr(mirror_service, 'FB_PATH', str(fb))
    monkeypatch.setattr(mirror_service.MirrorService, '_serve_loop', lambda self: None)

    order = []
    monkeypatch.setattr(mirror_service.os, 'system', lambda cmd: order.append(cmd))
    monkeypatch.setattr(gadget_linux, 'release_rndis_udc',
                        lambda: order.append('release') or True)
    monkeypatch.setattr(gadget_linux, 'restore_rndis',
                        lambda: order.append('restore') or True)
    return order


def test_start_releases_the_udc_before_loading_g_serial(env):
    svc = mirror_service.MirrorService()
    svc.start()
    try:
        assert env[0] == 'release', 'the RNDIS gadget must give up the UDC first'
        assert env[-1] == 'sudo modprobe g_serial'
    finally:
        svc.stop()


def test_stop_restores_the_network_after_unloading_g_serial(env):
    svc = mirror_service.MirrorService()
    svc.start()
    env.clear()
    svc.stop()

    assert 'sudo modprobe -r g_serial 2>/dev/null' in env
    assert env[-1] == 'restore', 'DHCP must be re-bound once usb0 is recreated'


def test_a_missing_gadget_does_not_break_the_mirror(env, monkeypatch):
    """Images without tools/rndis must keep working."""
    monkeypatch.setattr(gadget_linux, 'release_rndis_udc', lambda: False)
    monkeypatch.setattr(gadget_linux, 'restore_rndis', lambda: False)

    svc = mirror_service.MirrorService()
    svc.start()
    assert svc._running is True
    svc.stop()
    assert svc._running is False
