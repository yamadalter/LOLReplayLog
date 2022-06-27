# RGCustoms
A Discord bot to track customs with ROFL files. WIP

# Requirements  
Python module requirements are listed in requirements.txt. 
To generate images of matches/history/profiles, you will need to download the data dragon from Riot's API. 
You can find it here: https://developer.riotgames.com/docs/lol#data-dragon  
"runesReforged.json" needs to be put into data/, and the "img"   
directory from dragontail.zip should be moved here.

# image_gen  
image_gen generates images based on a given match history or particular match.  
![Match History Example](https://i.imgur.com/mGudOOW.png)  
![Match Example](https://i.imgur.com/X26ijaN.png)  
The background generated is transparent, to view the image in its entirety open the image in a new tab

# replay_reader  
replay_reader allows for data extraction from a .rofl file, or the .json inside of it.
