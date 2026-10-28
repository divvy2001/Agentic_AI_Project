# Bounce Keeper

## Spec

Create a tiny one-screen game called "Bounce Keeper". A paddle near the bottom of the window slides left and right with the arrow keys and stops at the screen edges. One ball bounces around the screen with realistic physics: it keeps its momentum, picks up spin when it hits the moving paddle, and rebounds naturally off the paddle and the left, right and top walls. Each time the ball bounces off the paddle the score goes up by 1 and the paddle flashes briefly with a quick squash animation. If the ball falls past the paddle, the game is over. Show the score in the top-left corner. When the game is over, show GAME OVER and the final score and stop the ball. Press R to restart with score 0 and Escape to quit. Print a line to the console every time a control takes effect: MOVE LEFT, MOVE RIGHT, RESTART and QUIT, and print GAME OVER when the game ends. Use plain coloured shapes only; no images or sounds. Keep it to one scene and as few scripts as possible.

## Notes

- Expected engine: godot
- Cheap Godot test: realistic ball physics. ~$0.10.
- Only the text under "## Spec" is sent to the Planner. This Notes section is ignored.
