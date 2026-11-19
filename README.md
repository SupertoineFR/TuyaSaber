## TuyaSaber
Make your lights come to life at the rythm of beat saber!  
**⚠ If you or someone else has epilepsy or is sensitive to flashing lights, DO NOT INSTALL THIS MOD ⚠**  


## Requirements
You'ill need
- A [TUYA wifi light](https://www.amazon.co.uk/tuya-light/s?k=tuya+light), or 2 of them
- [Beat saber](https://beatsaber.com/)
- [HttpSiraStatus](https://github.com/denpadokei/HttpSiraStatus)
- [websocket-sharp](https://github.com/sta/websocket-sharp) (install via [bsmanager](https://www.bsmanager.io/))

### Setup
1. Get your device's ID, IP and KEYS, a tutorial can be found here: [jasonacox/tinytuya#setup-wizzard](https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys)    
2. Replace the ID, IP, and key fields on lines 16–29 with your light's information(s) that you gathered in an earlier step.  
3. If the version needs to be changed fron the default of 3.3, line 80 is where it's stored (this needs fixing)
4. Run beat saber, then run the python script `python3 BeatSaber.py`
