"""Team Frotress 2 main module."""

# pylint: disable=logging-fstring-interpolation
# pylint: disable=anomalous-backslash-in-string

from __future__ import annotations

import logging
import re
import subprocess
import string
import asyncio
import sys
import os
import platform
import random
from pathlib import Path
from typing import Optional

from valve.rcon import RCON
from PIL import ImageGrab, Image
from ruamel.yaml import YAML
from buttplug import Client, WebsocketConnector
import numpy as np
from dxcam import DXCamera

import log_tailer
import vibration_handler

PLATFORM = platform.system()
print(f"Detected platform: {PLATFORM}")
if PLATFORM == "Windows":
    import dxcam

if not os.path.isfile("config.py"):
    print("Copy config_default.py to config.py and edit it to set up!")
    sys.exit()


# pylint: disable=too-many-statements
def get_uber_bar_region(resolution: tuple[int, int], os_platform: str) -> tuple[tuple[int, int, int, int], bool]:
    """
    Fetch the coords of the uber bar region based on the screen resolution.

    Parameters
    ----------
    resolution : tuple[int, int]
        The screen resolution (width, height).
    os_platform : str
        The operating system platform (Linux or Windows).

    Returns
    -------
    tuple[tuple[int, int, int, int], bool]
        The coordinates of the uber bar region (left, top, right, bottom) and a
        boolean indicating if medic uber support is enabled.
    """

    medic_uber_support = True
    logging.info(f"Detected platform: {os_platform}")
    if os_platform == "Linux":
        resolution_raw = (
            subprocess.Popen(
                'xrandr | grep "\*" | cut -d" " -f4', shell=True, stdout=subprocess.PIPE
            )  # pylint: disable=anomalous-backslash-in-string
            .communicate()[0]
            .split()[0]
            .split(b"x")
        )
        resolution = (int(resolution_raw[0].decode("UTF-8")), int(resolution_raw[1].decode("UTF-8")))
        if resolution == (1920, 1080):
            bar_center = (960, 744)
            bar_width = 340
            bar_height = 16
            bar_left = bar_center[0] - bar_width // 2
            bar_right = bar_center[0] + bar_width // 2
            bar_top = bar_center[1] - bar_height // 2
            bar_bottom = bar_center[1] + bar_height // 2
            full_bar_region = (bar_left, bar_top, bar_right, bar_bottom)
        elif resolution == (2560, 1440):
            bar_topleft = (1055, 984)
            bar_width = 450
            bar_height = 18
            bar_topright = (bar_topleft[0] + bar_width, bar_topleft[1])
            bar_bottomright = (bar_topright[0], bar_topright[1] + bar_height)
            full_bar_region = (
                bar_topleft[0],
                bar_topleft[1],
                bar_bottomright[0],
                bar_bottomright[1],
            )
        else:
            medic_uber_support = False
            full_bar_region = (0, 0, 0, 0)
            print(
                "Detected incompatible resolution! \
                    Currently supported resolutions are:\n1920x1080\nMedic Uber Charge functionality will not work"
            )
    # This does not check for resolution and really should
    elif os_platform == "Windows":
        print("Widows OS: Using provided resolution.")
        if resolution == (2560, 1440):
            bar_topleft = (1055, 984)
            bar_width = 450
            bar_height = 18
            bar_topright = (bar_topleft[0] + bar_width, bar_topleft[1])

            bar_bottomright = (bar_topright[0], bar_topright[1] + bar_height)
            full_bar_region = (
                bar_topleft[0],
                bar_topleft[1],
                bar_bottomright[0],
                bar_bottomright[1],
            )
            medic_uber_support = True
        elif resolution == (1920, 1080):
            bar_center = (960, 744)
            bar_width = 340
            bar_height = 16
            bar_left = bar_center[0] - bar_width // 2
            bar_right = bar_center[0] + bar_width // 2
            bar_top = bar_center[1] - bar_height // 2
            bar_bottom = bar_center[1] + bar_height // 2
            full_bar_region = (bar_left, bar_top, bar_right, bar_bottom)
            medic_uber_support = True
        else:
            medic_uber_support = False
            full_bar_region = (0, 0, 0, 0)
            print("Detected incompatible resolution! Compatible resolutions are 1920x1080 and 2560x1440")
    else:
        print(
            "Detected incompatible operating system! \
                Currently supported operating systems are:\nLinux and Windows"
        )
        raise NotImplementedError("Unsupported operating system")

    return full_bar_region, medic_uber_support


def get_colours_in_image(image: Image.Image) -> list[tuple[int, int, int]]:
    """
    Get the unique colours in the image.

    Parameters
    ----------
    image : Image.Image
        The image to check.

    Returns
    -------
    list[tuple[int, int, int]]
        A list of unique colours in the image (RGB tuples).
    """
    # Get the unique colours in the image
    colours = set(image.getdata())

    return list(colours)


def colour_in_image(image: Image.Image, colour: tuple[int, int, int]) -> bool:
    """
    Check if the image contains the specified colour.

    Parameters
    ----------
    image : Image.Image
        The image to check.
    colour : tuple[int, int, int]
        The colour to check for (RGB tuple).

    Returns
    -------
    bool
        True if the image contains the specified colour, False otherwise.
    """

    unique_colours = get_colours_in_image(image=image)
    if colour in unique_colours:
        return True
    else:
        return False


def only_colours_in_image(image: Image.Image, allowed_colours: list[tuple[int, int, int]]) -> bool:
    """
    Check if the image contains only the specified colours.

    Parameters
    ----------
    image : Image.Image
        The image to check.
    allowed_colours : list[tuple[int, int, int]]
        A list of allowed colours (RGB tuples).

    Returns
    -------
    bool
        True if the image contains only the specified colours, False otherwise.
    """

    unique_colours = get_colours_in_image(image=image)
    if set(unique_colours).issubset(set(allowed_colours)):
        return True
    else:
        return False


def colour_percentage(image: Image.Image, colour: tuple[int, int, int]) -> float:
    """
    Calculate the percentage of the specified colour in the image.

    Parameters
    ----------
    image : Image.Image
        The image to check (RGB mode).
    colour : tuple[int, int, int]
        The colour to check for (RGB tuple).

    Returns
    -------
    float
        The percentage of the specified colour in the image.
    """

    image_np = np.array(image)
    mask = np.all(image_np == colour, axis=-1)
    matching_pixels = np.sum(mask)
    total_pixels = image_np.shape[0] * image_np.shape[1]
    percentage = (matching_pixels / total_pixels) * 100
    return percentage


def uber_image_grabber(
    full_bar_region: tuple[int, int, int, int], os_platform: str, dxc: Optional[DXCamera] | None = None
) -> Image.Image:
    """
    Grabs the image of the full uber bar.

    Parameters
    ----------
    full_bar_region : tuple[int, int, int, int]
        The region of the screen to grab (left, top, right, bottom).
    os_platform : str
        The operating system platform (Linux or Windows).
    dxc : Optional[DXCamera]
        The DXCamera object to use for grabbing the image (Windows only).

    Returns
    -------
    Image.Image
        The image of the uber bar.
    """
    if os_platform == "Linux":
        return ImageGrab.grab(bbox=full_bar_region)
    elif os_platform == "Windows":
        assert dxc is not None, "DXCamera object is required for Windows"  # For type safety
        frame = None
        while frame is None:
            frame = dxc.grab(region=full_bar_region)
        return Image.fromarray(frame)
    else:
        raise NotImplementedError("Uber image grabber not implemented for this platform.")


def uber_percentage_grabber(
    uber_bar_region: tuple[int, int, int, int], os_platform: str, dxc: Optional[DXCamera], debug: bool, debug_dir: str
) -> tuple[int | None, str | None]:
    """
    Returns the current uber percentage calculated from a screengrab.

    Paramters
    ----------
    uber_bar_region : tuple[int, int, int, int]
        The region of the screen to grab (left, top, right, bottom).
    os_platform : str
        The operating system platform (Linux or Windows).
    dxc : DXCamera
        The DXCamera object to use for grabbing the image.
    debug : bool
        Whether to save the image for debugging.
    debug_dir : str
        The directory to save the image for debugging.

    Returns
    -------
    int
        The current uber percentage.
    """
    if os_platform == "Linux":
        img = uber_image_grabber(
            full_bar_region=uber_bar_region,
            os_platform=os_platform,
        )
    elif os_platform == "Windows":
        img = uber_image_grabber(
            full_bar_region=uber_bar_region,
            os_platform=os_platform,
            dxc=dxc,
        )
        if debug:
            # Save image for debugging
            img.save(f"{debug_dir}/uber_bar_region.png")

    colour_background = (24, 24, 24)
    colour_regular_fill = (255, 253, 252)
    colour_uber_max_or_draining = (184, 217, 255)

    # ensure that the image only contains the colours of the bar
    if not only_colours_in_image(
        image=img, allowed_colours=[colour_background, colour_regular_fill, colour_uber_max_or_draining]
    ):
        print("!! Uber requested but not visible")
        return None, None

    bar_status = "building"
    # if the filled colour is in the bar, then it's either full or draining
    if colour_in_image(img, colour=colour_uber_max_or_draining):
        filled_percentage = colour_percentage(img, colour=colour_uber_max_or_draining)
        if filled_percentage == 100:
            bar_status = "full"
        else:
            bar_status = "draining"
    else:
        # the bar is not full, so we calculate the percentage using the regular fill colour
        filled_percentage = colour_percentage(img, colour=colour_regular_fill)
        bar_status = "building"

    filled_percentage_int = int(filled_percentage)
    print(f"Uber bar status: {bar_status}, percentage: {filled_percentage_int}%")

    return filled_percentage_int, bar_status


async def main(app_config: dict, app_rcon: RCON, logfile: str, os_platform: str, dxc: Optional[DXCamera]) -> None:
    """
    Main function to run the Team Frotress 2 script.

    Parameters
    ----------
    config : dict
        The configuration dictionary.
    rcon : RCON
        The RCON object to use for sending commands.
    logfile : str
        The path to the TF2 console log file.
    os_platform : str
        The operating system platform (Linux or Windows).
    dxc : Optional[DXCamera]
        The DXCamera object to use for grabbing images (Windows only).
    """
    client = Client("Team Frotress 2")  # :3

    connector = WebsocketConnector(app_config["networking"]["intiface_server_addr"], logger=client.logger)

    console = log_tailer.LogTail(logfile)
    _ = console.read()

    try:
        await client.connect(connector)
    except Exception:  # pylint: disable=broad-except
        logging.error("Could not connect!")
        return

    client.logger.info("Connected to Intiface!")

    if len(client.devices) == 0:
        logging.error("No devices!")
        return

    logging.info("Executing Team Frotress config files")

    # enables class and weapon switch functionality
    app_rcon.execute("exec teamfrotress")
    if app_config["tf2"]["enable_weaponswitch"]:
        # anxious-doe: unsure what this does, leaving it alone
        app_rcon.execute("exec teamfrotress_switcher")

    # get steam username to detect killfeed data
    match_name = None
    logging.info("Getting name...")
    while match_name is None:
        try:
            name_response = app_rcon.execute("name")
            name_response_text = name_response.text
            match_name = re.match(
                pattern='"name" = "([^\n]+)" \( def. "unnamed" \)', string=name_response_text
            )  # pylint: disable=anomalous-backslash-in-string
        except UnicodeDecodeError:
            pass

    name = match_name[1]
    logging.info(f"Got name: {name}")

    logging.info("Ready to play!")

    current_uber = 0
    last_uber = 0
    currently_ubered = False
    curr_class = ""
    curr_weapon = -1
    resolution = tuple(app_config["tf2"]["resolution"])  # need to convert to tuple since yaml loads as list
    uber_bar_region, medic_uber_support = get_uber_bar_region(resolution=resolution, os_platform=os_platform)
    logging.info(f"Uber bar region: {uber_bar_region}, medic_uber_support: {medic_uber_support}")

    logging.info("Settign up vibe handler")
    vibe = vibration_handler.VibrationHandler(logging, app_rcon, config=app_config["vibe"])

    logging.info("### ready! ###")

    while True:
        # detect kills & class / weapon switches from console log
        while True:
            line = console.read_line()
            if line is None:
                break

            if switch_match := re.match(
                """\d\d\/\d\d\/\d\d\d\d - \d\d:\d\d:\d\d: teamfrotress_(\w+)""",
                string=line,
            ):
                if switch_match[1] in [
                    "scout",
                    "soldier",
                    "pyro",
                    "heavyweapons",
                    "demoman",
                    "engineer",
                    "medic",
                    "sniper",
                    "spy",
                ]:
                    curr_class = switch_match[1]
                    logging.info(f"New class: {curr_class}")
                    vibe.killstreak = 0
                    vibe.uberstreak = 0

                elif switch_match[1] in ["slot1", "slot2", "slot3"]:
                    curr_weapon = int(switch_match[1][-1])

            if killfeed_match := re.match(
                pattern="""\d\d\/\d\d\/\d\d\d\d - \d\d:\d\d:\d\d: ([^\n]{0,32}) killed ([^\n]{0,32}) with (\w+)\. ?(\(crit\))?""",  # pylint: disable=line-too-long
                string=line,
            ):

                if killfeed_match[1] == name:  # we got a kill
                    print(f"Kill logged, streak: {vibe.killstreak}{', crit' if killfeed_match[4] is not None else ''}")
                    vibe.kill(killfeed_match[4] is not None)
                if killfeed_match[2] == name:  # we died :(
                    logging.info("Death logged")
                    vibe.death()

        if curr_class == "medic" and medic_uber_support and (curr_weapon == 2 or curr_weapon == 3):
            uber_grabbed, bar_status = uber_percentage_grabber(
                uber_bar_region=uber_bar_region,
                os_platform=os_platform,
                dxc=dxc,
                debug=app_config["debug"],
                debug_dir=app_config["paths"]["debug_save_dir"],
            )
            # logging.info(f"New uber: {uber_grabbed}")
        else:
            uber_grabbed = None
            bar_status = "unknown"

        # handle uber
        # note that uber will not always be grabbable even while uber is active since switching to primary will hide
        # the bar.
        if uber_grabbed is not None:
            last_uber = current_uber
            current_uber = uber_grabbed

            if not currently_ubered:
                if bar_status == "draining":
                    # uber activated
                    logging.info("Activated Uber!")
                    currently_ubered = True
                    vibe.start_uber()

            # check for increase in uber - note this sometimes happens during an uber due to use of ubersaw
            if current_uber > last_uber:
                vibe.uber_milestone(current_uber, last_uber)

            # uber ended - threhold is 5% since the exact frame of 0 might be skipped
            if currently_ubered and (current_uber < 5):
                print(f"Uber ended, current: {current_uber}")
                currently_ubered = False
                vibe.end_uber()
        # ubered but bar not visible
        elif currently_ubered:
            # Last time we saw it, we were ubered, maybe figure out something, but for now, we have to wait to see the
            # bar again
            pass

        # run vibrator
        await vibe.run_buzz(devices=client.devices)
        await asyncio.sleep(1.0 / app_config["tf2"]["update_speed"])


if __name__ == "__main__":

    # Load yaml config from config.yaml
    yaml = YAML(typ="safe")
    with open(Path("config.yaml"), encoding="UTF-8") as f:
        config = yaml.load(f)

    config_paths = config["paths"]
    config_networking = config["networking"]
    config_tf2 = config["tf2"]
    config_vibe = config["vibe"]

    # Check for debugging mode
    debug_mode = config["debug"]
    debug_save_dir = config_paths["debug_save_dir"]
    if debug_mode:
        print(f"Debug mode enabled, saving debug logs to {debug_save_dir}")

    print("Press enter to launch TF2!")
    input()

    # Set up networking

    # For random password generation
    CHARS = string.digits + string.ascii_letters
    address = ("127.0.0.1", config_networking["rcon_port"])
    if os.path.isfile("rconpass.txt"):
        with open("rconpass.txt", mode="r", encoding="UTF-8") as f:
            RCON_PASSWORD = f.read().strip()
    else:
        RCON_PASSWORD = "".join([random.choice(CHARS) for i in range(32)])
        with open("rconpass.txt", mode="w", encoding="UTF-8") as f:
            f.write(RCON_PASSWORD)

    if PLATFORM == "Windows":
        tf2_args = [config_paths["tf2_game_executable"]]
    else:
        tf2_args = ["~/.steam/bin32/steam-runtime/run.sh", config_paths["tf2_game_executable"]]

    added_args = (
        " -game tf -steam -secure -usercon +developer 1 +alias developer +ip 0.0.0.0 +alias ip +sv_rcon_whitelist_address 127.0.0.1 +alias sv_rcon_whitelist_address +rcon_password "  # pylint: disable=line-too-long
        + RCON_PASSWORD
        + " +alias rcon_password +hostport "
        + str(config_networking["rcon_port"])
        + " +alias hostport +alias cl_reload_localization_files +net_start +con_timestamp 1 +alias con_timestamp -condebug -conclearlog "  # pylint: disable=line-too-long
        + config_tf2["extra_launch_options"]
    ).split()
    tf2_args.extend(added_args)

    print("Launching TF2 with the following arguments:")
    print(" ".join(tf2_args))
    subprocess.Popen(args=tf2_args)

    print("Wait until TF2 has made it to the main menu, then press enter")
    input()

    try:
        print("Connecting to RCON server at " + str(address) + " with password: " + RCON_PASSWORD)
        rcon = RCON(address=address, password=RCON_PASSWORD)
        rcon.connect()
        print("Connected to RCON server")
        rcon.authenticate()
    except Exception as e:  # pylint: disable=broad-except
        print(f"Could not connect to RCON server: {e}")
        exit()

    if PLATFORM == "Windows":
        DXCAMERA = dxcam.create()
    else:
        DXCAMERA = None

    print("Ensure Intiface Central is running and has your device connected, then press enter")
    input()

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    with open(config_paths["tf2_console_log"], mode="r", encoding="UTF-8") as f:
        asyncio.run(main(app_config=config, app_rcon=rcon, logfile=f, os_platform=PLATFORM, dxc=DXCAMERA))
