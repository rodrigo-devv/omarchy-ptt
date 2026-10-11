"""A focused X11 window receives only its own button events. No global grabs."""
from .config import DEFAULT, validate


class SelectionCancelled(RuntimeError):
    pass


def button_profile(button):
    if type(button) is not int or button not in range(8, 13):
        raise ValueError('Escolha um botão lateral Mouse8–Mouse12.')
    return validate(DEFAULT | {'linux_button': 275 + button - 8, 'x11_button': button})


def capture(display_name=None):
    from Xlib import X, XK, display
    connection = display.Display(display_name)
    screen = connection.screen()
    window = screen.root.create_window(100, 100, 600, 220, 0, screen.root_depth,
        X.InputOutput, X.CopyFromParent, background_pixel=screen.white_pixel,
        event_mask=X.ExposureMask | X.ButtonPressMask | X.ButtonReleaseMask | X.KeyPressMask)
    window.set_wm_name('Configuração PTT Discord - Omarchy PTT')
    window.set_wm_class('omarchy-ptt-configure', 'OmarchyPTTConfigure')
    delete = connection.intern_atom('WM_DELETE_WINDOW')
    window.set_wm_protocols([delete])
    gc = window.create_gc(foreground=screen.black_pixel)
    font = connection.open_font('fixed')
    gc.change(font=font.id)
    window.map()
    connection.flush()
    selected, released = None, False
    message = 'Posicione o cursor aqui e aperte o botão lateral desejado.'
    def draw():
        window.clear_area()
        for y, text in [(40, 'Configuração PTT Discord'), (85, message),
                        (130, 'Solte o botão. Enter confirma; Esc cancela.'),
                        (170, 'Depois, grave o mesmo botão no Discord se você o mudou.')]:
            window.draw_text(gc, 22, y, text.encode('latin1', errors='replace'))
        connection.flush()
    try:
        while True:
            event = connection.next_event()
            if event.type == X.Expose:
                draw()
            elif event.type == X.ButtonPress:
                try:
                    selected = button_profile(event.detail)
                    released = False
                    message = f'Mouse{event.detail} selecionado. Solte para continuar.'
                except ValueError as error:
                    selected, released = None, False
                    message = str(error)
                draw()
            elif event.type == X.ButtonRelease and selected and event.detail == selected['x11_button']:
                released = True
                message = f"Mouse{selected['x11_button']} pronto. Enter para salvar."
                draw()
            elif event.type == X.KeyPress:
                key = connection.keycode_to_keysym(event.detail, 0)
                if key == XK.XK_Escape:
                    raise SelectionCancelled('Configuração cancelada; nada foi alterado.')
                if key in (XK.XK_Return, XK.XK_KP_Enter) and selected and released:
                    return selected
            elif event.type == X.ClientMessage and event.data[1][0] == delete:
                raise SelectionCancelled('Configuração cancelada; nada foi alterado.')
    finally:
        window.destroy()
        gc.free()
        font.close()
        connection.close()
