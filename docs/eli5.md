# The Magic Laser Engraving Guide (Explain Like I'm 5!)

Welcome, young inventor! Today, we are going to learn how to prepare pictures for a **laser cutter** (which is basically a super-strong, hot robot flashlight) so it can draw your favorite pictures onto wood, leather, or acrylic!

---

## 1. What is a Laser Cutter and Why is it Confused?

Imagine drawing a picture. If you use a black marker on a white piece of wood, it's very easy to see. But what if you try to draw with a gray marker? The laser cutter doesn't have a "gray" marker. It only has a hot beam that can do two things:
1. **TURN ON** (burn black)
2. **TURN OFF** (leave wood white)

If you give the laser a gray picture, it gets confused. It tries to guess how hot to get, and sometimes it ends up burning your picture into a giant, charred puddle of charcoal!

Our magic tool takes your picture and turns it into a pattern of **only pure black dots and pure white spaces**. This way, the laser knows exactly when to turn on and when to turn off!

---

## 2. The Dot Magic (What is Dithering?)

How do we make something look gray if we only have black and white? 
Close your eyes and imagine a starry sky. If there are a million tiny white stars close together, that part of the sky looks light gray. If the stars are far apart, it looks dark.

This is called **Dithering**:
* We break your picture into millions of tiny dots.
* Where your picture is dark, we put the dots very close together.
* Where your picture is light, we spread the dots far apart.

Our tool uses a special recipe called **Atkinson Dithering**. It arranges the dots in a super-clean way so your edges stay sharp and don't get messy!

---

## 3. How to Use the Magic Tool

Making your pictures laser-ready is as easy as baking cookies:

1. **Drop Your Picture:** Put your favorite drawings or pictures into the folder named `input`.
2. **Tell the Robot to Start:** Open the terminal (the computer screen with the text prompt) and type:
   ```bash
   gf
   ```
3. **Get Your Magic Picture:** Look inside the folder named `output`. You will find your picture transformed into clean black-and-white dots, ready for the laser cutter!

---

## 4. Preset Superpowers (Choose Your Material!)

We have pre-programmed recipes (presets) so you don't have to guess the settings. Think of them like superpowers for different materials:

* **`--preset wood-hard` (Hard Wood Hero):** For engraving on dark woods like walnut. It burns a bit deeper so the picture pops!
* **`--preset wood-soft` (Soft Wood Friend):** For lighter woods like basswood. It keeps the laser gentle so it doesn't char the wood.
* **`--preset ai-art` (AI Monster Cleaner):** AI drawings often have fuzzy, invisible noise. This preset sweeps away the dust and makes the lines super crisp.
* **`--preset sketch` (Pencil Drawing):** Makes your digital pictures look like they were drawn by hand with a pencil.
* **`--preset stamp` (Stamp Maker):** Makes the engraving extra deep so you can create your own rubber ink stamps.

---

## 5. Making Your Own Wooden Coasters! 🪵

Do you want to make a circular wooden coaster with your favorite picture on it? We have a special preset called **`coaster`**!

Here is how the magic works:
1. **The Circle Cutout:** When you type `--preset coaster`, the tool draws a perfect circle around your picture and makes everything outside that circle disappear (transparent).
2. **The Cut Line:** The tool draws a thin, solid black circle line right at the edge.
3. **The Laser's Job:**
   * First, the laser **engraves** (burns) your picture inside the circle.
   * Second, the laser traces the outer black line and **cuts** the wood, popping out a perfect circular coaster!

To make a coaster that is 4 inches wide, just type:
```bash
gf --preset coaster -w 4
```
And ta-da! Your coaster file is ready to print. Have fun inventing!
