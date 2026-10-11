// Exercise the production plugin with Hyprland's real signal implementation.
// Compositor-specific event registration is stubbed; no desktop input is sent.
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <linux/input-event-codes.h>
#include <cassert>
#include <iostream>

APICALL PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE);
APICALL void PLUGIN_EXIT();

namespace {
UP<Event::CEventBus> eventBus = makeUnique<Event::CEventBus>();
SP<Event::CEventBus::CCustomEvent> registeredEvent;
bool compatible = true;
}

Log::CLogger::CLogger() = default;
CHyprColor::CHyprColor(float red, float green, float blue, float alpha) : r(red), g(green), b(blue), a(alpha) {}
UP<Event::CEventBus>& Event::bus() { return eventBus; }
Event::CEventBus::CCustomEvent::CCustomEvent(std::string name, std::vector<eType> types) : m_name(std::move(name)), m_argTypes(std::move(types)) {}
Event::CEventBus::CCustomEvent::~CCustomEvent() = default;
std::expected<void, std::string> Event::CEventBus::CCustomEvent::emit(const std::vector<ValidVariant>& args) {
    m_event.emit(args);
    return {};
}
APICALL EXPORT const char* __hyprland_api_get_hash() { return compatible ? __hyprland_api_get_client_hash() : "incompatible-build"; }
namespace HyprlandAPI {
APICALL bool addEvent(HANDLE, SP<Event::CEventBus::CCustomEvent> event) {
    assert(!registeredEvent);
    registeredEvent = event;
    return true;
}
APICALL bool removeEvent(HANDLE, const std::string& name) {
    assert(registeredEvent->m_name == name);
    registeredEvent.reset();
    return true;
}
}

int main() {
    compatible = false;
    try {
        PLUGIN_INIT(nullptr);
        assert(false && "An incompatible build must be rejected");
    } catch (const std::runtime_error&) {}
    assert(!registeredEvent);
    compatible = true;
    auto info = PLUGIN_INIT(nullptr);
    assert(info.name == "omarchy-ptt-release");
    int releases = 0;
    int lastButton = 0;
    auto listener = registeredEvent->m_event.listen([&](const auto& args) { ++releases; lastButton = std::get<int>(args.at(0)); });
    Event::SCallbackInfo callbackInfo;
    auto emit = [&](unsigned button, wl_pointer_button_state state) {
        eventBus->m_events.input.mouse.button.emit(IPointer::SButtonEvent{.button = button, .state = state}, callbackInfo);
    };
    emit(BTN_EXTRA, WL_POINTER_BUTTON_STATE_PRESSED);
    emit(BTN_LEFT, WL_POINTER_BUTTON_STATE_RELEASED);
    assert(releases == 0 && !callbackInfo.cancelled);
    // The workspace switch has cleared the compositor's held-button list.
    // No release bind runs, but the earlier raw release signal still arrives.
    emit(BTN_EXTRA, WL_POINTER_BUTTON_STATE_RELEASED);
    assert(releases == 1 && lastButton == BTN_EXTRA && !callbackInfo.cancelled);
    emit(BTN_SIDE, WL_POINTER_BUTTON_STATE_RELEASED);
    assert(releases == 2 && lastButton == BTN_SIDE);
    PLUGIN_EXIT();
    assert(!registeredEvent);
    emit(BTN_EXTRA, WL_POINTER_BUTTON_STATE_RELEASED);
    assert(releases == 2 && !callbackInfo.cancelled);
    std::cout << "PASS: ABI guard, Mouse9 filtering, release before discarded bind, clean unload\n";
}
