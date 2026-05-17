"""CONF view — configuration settings with persistent storage.

Settings are saved to disk immediately on change (not on app exit) so that
values survive crashes. The COORDS and CAM views re-read the config file
each time they're shown, ensuring changes take effect without restart.

Uses radio buttons and checkboxes instead of dropdowns because tkinter's
OptionMenu doesn't respond well to touchscreen taps (requires precise
press-hold-release gesture that's difficult on a 5" resistive screen).
"""

import tkinter as tk


def create(parent, fonts, config, save_config, config_file):
    """Create the CONF view frame and return it.

    Args:
        parent: parent tkinter widget
        fonts: dict with keys FONT_INFO, FONT_STATUS
        config: ConfigParser instance (shared with other views)
        save_config: callable to persist config to disk
        config_file: absolute path to config file
    Returns:
        frame: the conf_frame widget
    """
    frame = tk.Frame(parent, bg='black')

    tk.Label(frame, text="Configuration", font=fonts["FONT_INFO"],
             fg='white', bg='black').pack(pady=(20, 20))

    # ─── DMS decimals checkbox ───
    # Controls whether GPS seconds show decimals (18.99" vs 19").
    # BooleanVar is linked to the Checkbutton — tkinter updates it automatically.
    dms_decimal_var = tk.BooleanVar(
        value=config.getboolean("gps", "show_dms_decimals", fallback=False))

    def on_dms_toggle():
        """Save DMS decimal preference to config file immediately.

        Only saves to file here — the actual gps_core.SHOW_DMS_DECIMALS
        variable is updated when the user switches to COORDS view
        (via coords_on_show). This avoids tight coupling between views.
        """
        val = dms_decimal_var.get()
        config.set("gps", "show_dms_decimals", str(val))
        save_config(config)

    tk.Checkbutton(frame, text="Show decimal seconds in GPS coordinates",
                   variable=dms_decimal_var, command=on_dms_toggle,
                   font=fonts["FONT_STATUS"], fg='white', bg='black',
                   selectcolor='#333333',
                   activebackground='black',
                   activeforeground='white').pack(pady=10, padx=20, anchor='w')

    # ─── Camera rotation radio buttons ───
    # Radio buttons chosen over dropdown because they're easier to tap
    # on a touchscreen — each option is a separate large touch target.
    tk.Label(frame, text="Camera rotation:", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')

    cam_rotation_var = tk.StringVar(
        value=str(config.getint("cam", "rotation", fallback=0)))

    def on_rotation_change():
        """Save camera rotation to config file immediately.

        The CAM view reads this value every frame (not cached) so rotation
        changes take effect instantly without needing to re-enter CAM view.
        """
        if not config.has_section("cam"):
            config.add_section("cam")
        config.set("cam", "rotation", cam_rotation_var.get())
        save_config(config)

    rot_frame = tk.Frame(frame, bg='black')
    rot_frame.pack(padx=20, anchor='w')
    for val in ("0", "90", "180", "270"):
        tk.Radiobutton(rot_frame, text=f"{val}\u00b0",
                       variable=cam_rotation_var, value=val,
                       command=on_rotation_change, font=fonts["FONT_STATUS"],
                       fg='white', bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground='white',
                       indicatoron=1).pack(side='left', padx=10)

    # ─── Coordinate colors ───
    # Radio buttons for fix/no-fix coordinate colors.
    # Colors change in COORDS view to indicate whether position is current.
    if not config.has_section("coords"):
        config.add_section("coords")

    COLORS = [("green", "lime"), ("red", "red"), ("blue", "cyan"), ("yellow", "yellow")]

    # Fix color (when GPS has a valid position)
    tk.Label(frame, text="Position color (GPS fix):", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')
    fix_color_var = tk.StringVar(value=config.get("coords", "fix_color", fallback="lime"))

    def on_fix_color():
        config.set("coords", "fix_color", fix_color_var.get())
        save_config(config)

    fix_color_frame = tk.Frame(frame, bg='black')
    fix_color_frame.pack(padx=20, anchor='w')
    for label, value in COLORS:
        tk.Radiobutton(fix_color_frame, text=label, variable=fix_color_var, value=value,
                       command=on_fix_color, font=fonts["FONT_STATUS"],
                       fg=value, bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground=value,
                       indicatoron=1).pack(side='left', padx=10)

    # No-fix color (when GPS lost fix, showing stale position)
    tk.Label(frame, text="Position color (no fix):", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')
    nofix_color_var = tk.StringVar(value=config.get("coords", "nofix_color", fallback="red"))

    def on_nofix_color():
        config.set("coords", "nofix_color", nofix_color_var.get())
        save_config(config)

    nofix_color_frame = tk.Frame(frame, bg='black')
    nofix_color_frame.pack(padx=20, anchor='w')
    for label, value in COLORS:
        tk.Radiobutton(nofix_color_frame, text=label, variable=nofix_color_var, value=value,
                       command=on_nofix_color, font=fonts["FONT_STATUS"],
                       fg=value, bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground=value,
                       indicatoron=1).pack(side='left', padx=10)

    # ─── Error/warning message color ───
    tk.Label(frame, text="Error message color:", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')

    error_color_var = tk.StringVar(value=config.get("coords", "error_color", fallback="red"))

    def on_error_color():
        config.set("coords", "error_color", error_color_var.get())
        save_config(config)

    error_color_frame = tk.Frame(frame, bg='black')
    error_color_frame.pack(padx=20, anchor='w')
    for label_text, value in [("red", "red")]:
        tk.Radiobutton(error_color_frame, text=label_text, variable=error_color_var, value=value,
                       command=on_error_color, font=fonts["FONT_STATUS"],
                       fg=value, bg='black', selectcolor='#333333',
                       activebackground='black', activeforeground=value,
                       indicatoron=1).pack(side='left', padx=10)

    return frame
