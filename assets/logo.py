from PIL import Image
# for unitiated, I use this script to make the ico file actually look good in windows.
# better than any png to ico converters online meow :3
img = Image.open("logo.png")
sizes = [(16,16), (32,32), (48,48), (256,256)]
img.save("logo.ico", format="ICO", sizes=sizes)
