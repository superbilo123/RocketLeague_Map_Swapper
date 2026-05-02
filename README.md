# RocketLeague Map Swapper

A Windows desktop app for loading custom Rocket League maps without touching game files manually.

## What it does

Custom maps for Rocket League are distributed as `.upk` files that replace the standard Underpass map (`Labs_Underpass_P.upk`). This tool manages that swap for you. It keeps a backup of your original Underpass file and restores it on demand, so you can switch between custom maps and the default without doing anything manually.
To use the custom map, just select Underpass as your freeplay map and enjoy the loaded map.

## Requirements

- Windows 10 or 11
- Rocket League installed via Epic Games
- Custom map files downloaded from [bakkesplugins.com/maps](https://bakkesplugins.com/maps) (each map in its own subfolder containing a `.upk` file)

## Setup

1. Download and run `RL_Map_Swapper.exe`
2. Set your Maps Folder to wherever you keep your downloaded map subfolders
3. Set CookedPCConsole to your Rocket League install path (default is pre-filled)
4. Click Save

## Usage

- Click any map row to preview it
- Click Load to activate a map
- Click "Use Standard Underpass" to restore the original map
- Star maps to favourite them and filter the list

## ! Disclaimer

Use at your own risk. Since custom maps swap out a game file, it's a good idea to launch Rocket League without anti-cheat when playing with one loaded. You can do this by right-clicking (or clicking the three dots on) Rocket League in your Epic Games library and selecting "Launch without Anti-Cheat". If you're jumping into online matches, it's also worth restoring the original Underpass map first just to be safe.

## Notes

- The app may need to run as Administrator depending on your Rocket League install location
- Settings are saved to `%APPDATA%\RLmapswapper-config\config.json`
- The original Underpass file is backed up automatically the first time you load a custom map

## License

MIT
