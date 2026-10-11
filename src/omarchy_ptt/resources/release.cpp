#include <hyprland/src/plugins/PluginAPI.hpp>
#include <linux/input-event-codes.h>
#include <stdexcept>
#include <string>

namespace {
constexpr auto RELEASE_EVENT = "omarchy.ptt.button.release";
HANDLE pluginHandle = nullptr;
SP<Event::CEventBus::CCustomEvent> releaseEvent;
CHyprSignalListener buttonListener;
}

APICALL EXPORT std::string PLUGIN_API_VERSION() {
    return HYPRLAND_API_VERSION;
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    // Refuse incompatible compositor/dependency builds before registering callbacks.
    if (std::string(__hyprland_api_get_hash()) != __hyprland_api_get_client_hash())
        throw std::runtime_error("Omarchy PTT: Hyprland build mismatch");

    pluginHandle = handle;
    releaseEvent = makeShared<Event::CEventBus::CCustomEvent>(RELEASE_EVENT,
        std::vector<Event::CEventBus::CCustomEvent::eType>{Event::CEventBus::CCustomEvent::TYPE_INT});
    if (!HyprlandAPI::addEvent(handle, releaseEvent)) {
        releaseEvent.reset();
        throw std::runtime_error("Could not register the PTT release event");
    }

    // This event precedes onMouseButton's held-button check. Workspace switches
    // in 0.56.2 clear that list and discard the physical release before binds run.
    // Observe side-button releases; Lua filters the configured button.
    // Do not cancel input or alter held buttons.
    buttonListener = Event::bus()->m_events.input.mouse.button.listen([](const IPointer::SButtonEvent& event, Event::SCallbackInfo&) {
        if (event.button >= BTN_SIDE && event.button <= BTN_TASK && event.state == WL_POINTER_BUTTON_STATE_RELEASED)
            (void)releaseEvent->emit({static_cast<int>(event.button)});
    });

    return {"omarchy-ptt-release", "Preserve PTT release across workspace switches", "Omarchy PTT contributors", "0.1.0"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    buttonListener.reset();
    if (releaseEvent) {
        HyprlandAPI::removeEvent(pluginHandle, RELEASE_EVENT);
        releaseEvent.reset();
    }
    pluginHandle = nullptr;
}
