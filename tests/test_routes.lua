-- Run the real Lua bindings with simulated compositor events, without input.
local path = arg[1] or "discord-ptt-bridge.lua"
local subscriptions, binds, events, xwayland, has_plugin
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
  hl = {
    dsp = { event = function(action) return action end },
    dispatch = function(action) table.insert(events, action:match("omarchy%-ptt:(.*)")) end,
    unbind = function() end,
    get_window = function() return {} end,
    get_active_window = function() return { xwayland = xwayland } end,
    get_loaded_plugins = function() return has_plugin and {{ name = "omarchy-ptt-release" }} or {} end,
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
