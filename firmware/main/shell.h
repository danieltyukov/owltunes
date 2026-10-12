#pragma once

/* Start the USB console: @owl lines go to the setup protocol, every other line is a developer
 * command (docs/console.md). name is the owl's name for the "info" answer. */
void shell_start(const char *name);
