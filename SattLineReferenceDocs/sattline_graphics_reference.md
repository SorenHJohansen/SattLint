# SattLine Graphics, Modules, Interaction Objects, and Window Management — Unified Overview

---

## 1. Modules

### What a Module Is
A **module** is a container for graphical objects that behaves as a single object when closed.

### Core Capabilities
- Move, resize, reshape, rotate, flip
- Duplicate and delete
- Stack order can be changed relative to other modules
- All contained objects follow transformations  
  - **Exception:** text never rotates

### Duplication Behavior
- **Normal modules:** new instance, same module type
- **Single / Frame modules:** instance *and* type are duplicated

### Module vs Graphics
- Graphical objects are always drawn **below** modules
- Modules always stay visually on top

---

## 2. Module Attributes

### Visibility & State
- **Enable** – show/hide module
- **In view** – true if visible on screen
- **Dim** – dimmed display
- **Zoomable** – allows zoom tools

### Geometry
- X / Y position
- Rotation
- X / Y scale

All attributes can be:
- Constant
- Linked to variables
- Used for animation

---

## 3. Module Animation

- Real variables can drive:
  - Translation
  - Rotation
  - Scaling
- Min/max values define motion range
- Plus/minus reference points define direction and limits
- Rotation uses a configurable **origin point**

---

## 4. Basic Graphical Objects

### Primitives
- Line
- Rectangle
- Oval
- Polygon
- Polyline
- Segment
- Text

### Editing
- Drawn by click-click or click-drag
- Select individually or with selection frame
- Move, reshape, duplicate, delete
- Change stacking order

---

## 5. Dynamic Graphics

Variables can control:
- Visibility
- Colour
- Shape (via handle movement)

Handle movement:
- Linked to real variables
- Limited by min/max ranges

---

## 6. Text Objects

### Characteristics
- Single-line (max 100 characters)
- Fixed-size or auto-scaled inside a box

### Variable Display
Supports:
- Integer
- Real
- String
- Time
- Duration

Formatting options:
- Alignment
- Width
- Decimals
- Time/duration format

---

## 7. Interaction Objects

Used for operator interaction with variables and UI.

### 7.1 Graphical Interaction Objects
- Command buttons
- Text boxes
- Check boxes
- Option buttons

### 7.2 Non-Graphical Interaction Objects
- Invisible in Operate mode
- Placed as “hot zones” on graphics
- Same functionality as graphical versions

### Supported Variable Types
- Boolean
- Integer
- Real
- String
- Time
- Duration

---

## 8. Common Interaction Attributes

| Attribute | Meaning |
|---------|--------|
| Enable | Object is active |
| Visible | Object is shown |
| Key | Keyboard shortcut |
| Key global | Shortcut works even if hidden |
| Changed | Operator modified value |
| Selected | Object was activated |

---

## 9. Special Interaction Objects

### 9.1 Window Interaction Objects

Used to manage operator windows dynamically.

| Object | Function |
|------|---------|
| **NewWindow** | Creates window if not already present |
| **DeleteWindow** | Deletes window with given path |
| **ToggleWindow** | Creates or deletes window |

**Notes**
- Windows exist only during runtime
- Returning to Edit mode removes them
- Rotated modules reset unless wrapped in a **frame module**
- Wildcards supported for mass removal
- Double-click “–” closes all dynamic windows

---

### 9.2 Text Editor Interaction Objects

Used to open runtime text editors.

| Object | Function |
|------|---------|
| **NewEditFile** | Creates editor |
| **DeleteEditFile** | Removes editor |
| **ToggleEditFile** | Toggles editor |

**Notes**
- Separate from SattLine code editor
- Supports wildcards
- Works in Operate and Simulate modes

---

## 10. Composite Objects

### 10.1 Picture Display

Displays:
- A **module**, or
- A picture file (`.wmf`, `.emf`)

Works in:
- Edit
- Operate
- Run
- Simulate

#### Key Concepts
- Content defined by **path string**
- Path can be constant or variable
- Integer index variable can select from a path table

#### Behaviour
- No distortion
- Centred automatically
- Rotation ignored
- Zooming bitmaps deeply may be slow

#### Error Handling
- Errors shown as **red frame**
- Click → Information for details
- Causes: invalid paths, missing files, unresolved variables

---

### 10.2 String Selector

Displays one string from a table using an integer index.

Features:
- Table of strings
- Optional *Otherwise* string
- Visual frame indicator
- Recommended to wrap in a module for reuse

---

### 10.3 Bar Graph

Displays one or more real variables as bars.

Capabilities:
- Vertical or horizontal layout
- Multiple bars
- Grid lines
- Min/max limit colouring
- Variable-driven scale limits
- Variable-driven reference axis
- Optional operator-adjustable scale

Visibility controlled by boolean variable.

---

## 11. Window Management

### 11.1 Program Unit Windows
- Every program has a **Base window**
- Programs can appear in multiple windows
- Windows are containers for views

Used in:
- Edit mode
- Operate mode

---

### 11.2 Window Creation
- Double-click program icon
- Or `Window > New extra window`

Multiple windows appear as:
ProgramName:1
ProgramName:2

---

### 11.3 Window Properties
- Resize, move, minimize, maximize
- Closing window does not unload program
- Libraries hidden in Operate mode
- Recommended fixed aspect ratio: **20:14**

**Fixed Position Windows**
- Cannot be moved or resized
- No title bar or borders
- Still closable via `ALT+F4`

---

## 12. Views

A **view** is the visible portion of a program inside a window.

### View Operations
- Zoom
- Pan
- Center
- Reset to top level
- Copy between windows
- Assign to function keys

---

## 13. Window Content Interaction Object

- Replaces current window content with referenced module
- Multiple can exist in one module
- Enables fast navigation without opening new windows

---

## 14. Common Window & Editor Attributes

| Attribute | Description |
|---------|-------------|
| Relative pos | Position relative to object or main window |
| xPos / yPos | Lower-left corner |
| xSize / ySize | Window size (screen-limited) |
| HierarchicRoot | Makes window a sub-window |
| SelectClass | Ensures single window per class |
| TimeOut | Auto-close after inactivity |
| WindowDisplayed | Boolean state output |
| Enable / Key / Selected / Changed | Same as other interaction objects |

---

## 15. Practical Design Notes

- Stabilize module structure before adding Picture displays
- Use frame modules to preserve rotation in operator windows
- Prefer modules for reusable UI elements
- Keep interaction objects simple and predictable for operators
- Align to grid (even steps) for best visual consistency

---
