# The Magic Picture-Prep Guide (Explain Like I’m 5!)

Welcome, young inventor! This little program helps prepare pictures for a Glowforge. It can turn a photo into a pattern of tiny black and white dots, and it can save a shape outline as a vector path.

## 1. The picture and the laser are different things

A photo has lots of shades of gray. This program changes the photo into black and white dots so it can be used as an engraving picture. The Glowforge app then prepares the design for the machine. The dot picture does **not** tell us exactly what the finished wood will look like. The material and the machine’s approved settings matter too.

The project’s default stock note is **medium maple plywood, about 1/8 inch thick**. The thickness note can be changed with `--material-thickness`, for example `--material-thickness 1/4`. Ask the makerspace helper to check the sheet’s label and measure it. Different plywood can have different glue or layers, so a similar name does not mean the same material.

## 2. How can black and white look gray?

Imagine drawing with a black pen on clean white paper. If you place thousands of tiny black dots very close together, that part looks dark or black from a distance. If you spread the dots far apart with lots of white paper showing through, that part looks light gray. This dot trick is called **dithering**. The program uses a pattern called Atkinson dithering.

## 3. Try the program

1. Put your picture in the `input` folder.
2. Ask a grown-up or makerspace helper to use the computer terminal and type:

   ```bash
   gf
   ```
3. Look for the prepared picture in `output`.
4. Open it in the Glowforge app and check the picture, size, material, and print steps with the machine helper before anyone starts a print.

The tool’s presets change the picture. They do not choose the laser’s power or make a material safe.

## 4. Shape pictures

The `coaster` preset makes a picture with a circle-shaped transparent edge. The `coaster-heart` preset makes a heart-shaped edge. Example:

```bash
gf --input input/art.png --preset coaster --svg-cut -w 4 -h 4
```

This makes a 4-by-4-inch canvas, an engraving PNG, and an SVG file with a vector outline. A black line inside a PNG is still part of the picture and engraves. The vector line in the SVG can be assigned a cut or score operation in the Glowforge app. A grown-up must check that the art and line match before printing.

## 5. Make art, then check it

Try a photo, a drawing, a pet portrait, or a picture made with an AI art tool. The program can prepare pictures, but it does not draw the words, cut layouts, or a whole set of coaster shapes for you. Ask an adult to help choose safe material and follow the makerspace rules around the laser.

For the full command list, see the [handbook](handbook.md).
