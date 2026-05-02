"""CONF view — configuration settings with persistent storage."""

import tkinter as tk


def create(parent, fonts, config, save_config, config_file):
    """Create the CONF view frame and return it.

    Args:
        parent: parent tkinter widget
        fonts: dict with keys FONT_INFO, FONT_STATUS
        config: ConfigParser instance
        save_config: callable to persist config
        config_file: absolute path to config file
    Returns:
        frame: the conf_frame widget
    """
    frame = tk.Frame(parent, bg='black')

    tk.Label(frame, text="Configuration", font=fonts["FONT_INFO"],
             fg='white', bg='black').pack(pady=(20, 20))

    # ─── DMS decimals checkbox ───
    dms_decimal_var = tk.BooleanVar(
        value=config.getboolean("gps", "show_dms_decimals", fallback=False))

    def on_dms_toggle():
        """Save DMS decimal preference to config file."""
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
    tk.Label(frame, text="Camera rotation:", font=fonts["FONT_STATUS"],
             fg='white', bg='black').pack(pady=(20, 5), padx=20, anchor='w')

    cam_rotation_var = tk.StringVar(
        value=str(config.getint("cam", "rotation", fallback=0)))

    def on_rotation_change():
        """Save camera rotation to config file."""
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

    return frame
