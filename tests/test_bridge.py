from _support import ROOT
from omarchy_ptt import bridge
import unittest



class HoldLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.state = bridge.HoldState(self.events.append)

    def test_wayland_hold_has_no_release_until_actual_up(self):
        self.state.accept_line(b"custom>>omarchy-ptt:down")
        self.state.accept_line(b"workspace>>2")
        self.state.accept_line(b"activewindow>>some-window,ignored")
        self.assertEqual(self.events, [True])
        self.state.accept_line(b"custom>>omarchy-ptt:up")
        self.assertEqual(self.events, [True, False])

    def test_native_press_is_not_duplicated(self):
        self.state.handle("native-down")
        self.assertEqual(self.events, [])
        self.state.handle("up")
        self.assertEqual(self.events, [False])

    def test_native_hold_survives_focus_switch_to_wayland(self):
        self.state.handle("native-down")
        self.state.handle("promote")
        self.state.handle("up")
        self.assertEqual(self.events, [True, False])

    def test_duplicate_press_and_release_do_not_retoggle(self):
        for action in ["down", "down", "up", "up"]:
            self.state.handle(action)
        self.assertEqual(self.events, [True, False])

    def test_reload_releases_and_allows_a_new_hold(self):
        self.state.handle("down")
        self.state.accept_line(b"configreloaded>>")
        self.state.handle("down")
        self.state.handle("up")
        self.assertEqual(self.events, [True, False, True, False])

    def test_exit_cleanup_releases_both_routes(self):
        for press in ["down", "native-down"]:
            events = []
            state = bridge.HoldState(events.append)
            state.handle(press)
            state.handle("reset")
            self.assertIsNone(state.mode)
            self.assertEqual(events[-1], False)


if __name__ == "__main__":
    unittest.main()
