-- Run the real Lua bindings with simulated compositor events, without input.
local path = arg[1] or "discord-ptt-bridge.lua"
local subscriptions, binds, events, xwayland, has_plugin, guards, timers
local getenv = os.getenv
local io_open = io.open
os.getenv = function(key)
  if key == "XDG_RUNTIME_DIR" then return "/tmp" end
  if key == "HYPRLAND_INSTANCE_SIGNATURE" then return "test-instance" end
  return getenv(key)
end
io.open = function(file, mode)
  if file == "/tmp/omarchy-ptt.ready" then
    local line = 0
    return { read = function()
      line = line + 1
      local values = {"test-instance", tostring(os.time()), "idle", "123", arg[2]}
      return values[line]
    end, close = function() end }
  end
  return io_open(file, mode)
end

local function setup(plugin)
  _G.omarchy_ptt = nil
  subscriptions, binds, events, xwayland, has_plugin = {}, {}, {}, false, plugin
  guards, timers = {}, {}
  hl = {
    dsp = { event = function(action) return action end },
    dispatch = function(action) table.insert(events, action:match("omarchy%-ptt:(.*)")) end,
    unbind = function() end,
    get_window = function() return {} end,
    get_active_window = function() return { xwayland = xwayland } end,
    get_loaded_plugins = function() return has_plugin and {{ name = "omarchy-ptt-release" }} or {} end,
    window_rule = function(rule)
      assert(rule.match.xwayland and rule.focus_on_activate == false)
      local guard = { enabled = true, set_enabled = function(self, value) self.enabled = value end }
      table.insert(guards, guard)
      return guard
    end,
    timer = function(callback, opts)
      assert(opts.timeout == 200 and opts.type == "oneshot")
      local timer = { callback = callback, enabled = true, set_enabled = function(self, value) self.enabled = value end }
      table.insert(timers, timer)
      return timer
    end,
    on = function(name, callback)
      subscriptions[name] = callback
      return { remove = function() subscriptions[name] = nil end }
    end,
  }
  o = { window = function() end, bind = function(_, _, callback, opts) binds[opts.release and "up" or "down"] = callback end }
  dofile(path)
end

setup(true)
binds.down()
subscriptions["workspace.active"]()
assert(table.concat(events, ",") == "down", "Workspace change must preserve a held bridge PTT")
subscriptions["omarchy.ptt.button.release"](275)
assert(table.concat(events, ",") == "down", "Another mouse button must not release PTT")
-- Reproduce 0.56.2: physical release arrives, but no release bind is invoked.
subscriptions["omarchy.ptt.button.release"](276)
assert(table.concat(events, ",") == "down,up", "Physical release must end PTT even if the bind is lost")
assert(_G.omarchy_ptt.route == nil)
binds.up()
assert(table.concat(events, ",") == "down,up", "The ordinary bind must not emit a second release")
binds.down()
subscriptions["omarchy.ptt.button.release"](276)
assert(table.concat(events, ",") == "down,up,down,up", "Next press must work without an extra click")

setup(true)
xwayland = true
assert(binds.down().ok == false, "Native X11 press must remain unconsumed")
subscriptions["workspace.active"]()
subscriptions["omarchy.ptt.button.release"](276)
assert(table.concat(events, ",") == "native-down,promote,up", "Workspace switch must preserve native PTT too")

setup(false)
binds.down()
subscriptions["workspace.active"]()
assert(table.concat(events, ",") == "down,up", "Unavailable observer must release safely on workspace switch")
print("PASS: held workspace switch, lost release bind, release deduplication, next hold, native switch, fallback")

setup(true)
xwayland = true
binds.down()
assert(#guards == 1 and guards[1].enabled, "Native PTT must protect other XWayland clients before passing input")
subscriptions["omarchy.ptt.button.release"](276)
assert(guards[1].enabled, "Keep protection through asynchronous X11 release")
binds.down()
assert(not timers[1].enabled and #guards == 1, "A rapid new hold cancels pending cleanup and reuses protection")
subscriptions["omarchy.ptt.button.release"](276)
assert(#timers == 1 and timers[1].enabled, "Reuse the timer after a rapid new hold")
timers[1].callback()
assert(not guards[1].enabled and _G.omarchy_ptt.focus_guard ~= nil, "Restore normal activation after release settles")
binds.down()
subscriptions["hyprland.shutdown"]()
assert(not guards[1].enabled, "Shutdown must remove the guard")
binds.down()
dofile(path)
assert(not guards[2].enabled, "Reload must remove the previous hold's guard")
assert(_G.omarchy_ptt.focus_guard == nil, "Idle reload must not block activation")
print("PASS: temporary activation protection, release grace, rapid repress, shutdown and reload cleanup")
