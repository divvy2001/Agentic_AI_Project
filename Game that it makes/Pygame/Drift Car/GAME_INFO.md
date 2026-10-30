# Drift Car

- Engine: pygame
- Built: run 20261030_145932
- Result: GAME READY
- Spec file: drift_car.md
- Play: double-click `play.bat`

## Spec

Create a top-down car game called "Drift Car" where a car accelerates forward with Up and brakes/reverses with Down, steers left and right with the arrow keys, and carries realistic momentum and drift — the car keeps sliding in its prior direction of travel when turning at speed rather than snapping instantly to the new heading, and gradually loses speed from friction when no key is pressed. The car must stay within a race track boundary drawn as a closed loop of walls; crossing a lap-start line after going all the way around adds 1 lap. Hitting a wall briefly stops the car's forward momentum. Generate exactly one small image asset: the car, rotated to face its direction of travel. The track winds through a sunset desert canyon, with dusty rock cliffs and scattered cacti lining the course, giving the whole scene a warm, dusty rally atmosphere. Draw the track walls and lap line as plain coloured shapes, no other images. Show lap count in the top-left corner at all times. Press R to restart with 0 laps. Press Escape to quit. Print a line to the console every time a control takes effect: ACCELERATE, BRAKE, TURN LEFT, TURN RIGHT, RESTART and QUIT, and print LAP COMPLETE each time a lap finishes. No sounds. Keep it to as few files as possible. use pygame
