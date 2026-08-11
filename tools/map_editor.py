import json
import os
import tkinter as tk
from tkinter import filedialog
from ursina import *

app = Ursina(development_mode=False)
window.exit_button.visible = False
window.color = color.rgb(15, 18, 30)

# --- EDITOR CAMERA ---
editor_cam = EditorCamera()
editor_cam.rotation = (30, 45, 0)
editor_cam.position = (0, 10, -30)

# --- GRID FLOOR ---
floor = Entity(
    model='cube',
    position=(0, -1, 0),
    scale=(300, 2, 300),
    color=color.rgb(30, 35, 50),
    collider='box',
    unlit=True
)
floor.tag = "ground"

spawned_objects = []
selected_object = None
selection_indicator = Entity(model='wireframe_cube', color=color.yellow, scale=(1.1, 1.1, 1.1), enabled=False, unlit=True)

# --- UI PANEL (Fixed with unlit=True to prevent blinding light washout) ---
panel = Entity(parent=camera.ui, model='quad', color=color.rgba(10, 15, 30, 240), scale=(0.32, 0.95), position=(-0.68, 0), unlit=True)

Text(parent=panel, text="THREE·DOTS MAP BUILDER", position=(-0.42, 0.44), scale=0.9, color=color.rgb(0, 230, 255), unlit=True)
Entity(parent=panel, model='quad', color=color.rgba(0, 230, 255, 100), scale=(0.9, 0.002), position=(0, 0.40), unlit=True)

info_text = Text(parent=panel, text="Selected: None", position=(-0.42, 0.32), scale=0.6, color=color.rgb(200, 200, 200), unlit=True)

def update_info_text():
    if selected_object and selected_object in spawned_objects:
        pos = selected_object.position
        scale = selected_object.scale
        info_text.text = f"Selected: {selected_object.tag}\nPos: ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f})\nScale: ({scale.x:.1f}, {scale.y:.1f}, {scale.z:.1f})"
        selection_indicator.enabled = True
        selection_indicator.position = selected_object.position
        selection_indicator.scale = selected_object.scale * 1.05
    else:
        info_text.text = "Selected: None"
        selection_indicator.enabled = False

def spawn_object(model_type="cube", tag="prop", scale=(5, 5, 5), col=color.rgb(0, 120, 220)):
    global selected_object
    e = Entity(
        model=model_type,
        position=editor_cam.position + (editor_cam.forward * 15),
        scale=scale,
        color=col,
        collider='box',
        unlit=True
    )
    e.tag = tag
    spawned_objects.append(e)
    selected_object = e
    update_info_text()

def add_block():
    spawn_object("cube", "prop", (8, 5, 8), color.rgb(40, 100, 200))

def add_wall():
    spawn_object("cube", "wall", (40, 20, 4), color.rgb(0, 60, 150))

def add_pillar():
    spawn_object("cube", "pillar", (6, 25, 6), color.rgb(20, 40, 90))

def add_target():
    spawn_object("cube", "target", (8, 8, 1), color.rgb(0, 220, 200))

def delete_selected():
    global selected_object
    if selected_object and selected_object in spawned_objects:
        spawned_objects.remove(selected_object)
        destroy(selected_object)
        selected_object = None
        update_info_text()

def save_map_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")], initialfile="my_custom_map.json")
    root.destroy()
    
    if file_path:
        map_data = []
        for obj in spawned_objects:
            c = obj.color
            map_data.append({
                "tag": getattr(obj, "tag", "prop"),
                "position": [float(obj.x), float(obj.y), float(obj.z)],
                "scale": [float(obj.scale_x), float(obj.scale_y), float(obj.scale_z)],
                "color": [float(c.r), float(c.g), float(c.b), float(c.a)]
            })
        with open(file_path, "w") as f:
            json.dump(map_data, f, indent=4)
        print(f"Map saved successfully to {file_path}")

def load_map_file():
    global spawned_objects, selected_object
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")], title="Load Map JSON")
    root.destroy()
    
    if file_path:
        for obj in spawned_objects:
            destroy(obj)
        spawned_objects.clear()
        selected_object = None
        
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                for item in data:
                    col_vals = item.get("color", [1, 1, 1, 1])
                    col = color.Color(col_vals[0], col_vals[1], col_vals[2], col_vals[3])
                    e = Entity(
                        model="cube",
                        position=Vec3(item["position"][0], item["position"][1], item["position"][2]),
                        scale=Vec3(item["scale"][0], item["scale"][1], item["scale"][2]),
                        color=col,
                        collider="box",
                        unlit=True
                    )
                    e.tag = item.get("tag", "prop")
                    spawned_objects.append(e)
            print("Map loaded successfully!")
        except Exception as ex:
            print(f"Error loading map: {ex}")
        update_info_text()

# --- UI BUTTONS (Using unlit text colors & backgrounds) ---
Button(parent=panel, text="+ Add Block", position=(0, 0.18), scale=(0.85, 0.06), color=color.rgb(0, 80, 160), text_color=color.white, on_click=add_block)
Button(parent=panel, text="+ Add Wall", position=(0, 0.10), scale=(0.85, 0.06), color=color.rgb(0, 80, 160), text_color=color.white, on_click=add_wall)
Button(parent=panel, text="+ Add Pillar", position=(0, 0.02), scale=(0.85, 0.06), color=color.rgb(0, 80, 160), text_color=color.white, on_click=add_pillar)
Button(parent=panel, text="+ Add Target", position=(0, -0.06), scale=(0.85, 0.06), color=color.rgb(0, 150, 120), text_color=color.white, on_click=add_target)

Button(parent=panel, text="Delete Selected (Del)", position=(0, -0.18), scale=(0.85, 0.06), color=color.rgb(180, 40, 40), text_color=color.white, on_click=delete_selected)

Button(parent=panel, text="Save Map JSON", position=(0, -0.30), scale=(0.85, 0.06), color=color.rgb(40, 130, 40), text_color=color.white, on_click=save_map_file)
Button(parent=panel, text="Load Map JSON", position=(0, -0.38), scale=(0.85, 0.06), color=color.rgb(80, 80, 80), text_color=color.white, on_click=load_map_file)

def input(key):
    global selected_object
    if key == 'left mouse down':
        if not mouse.hovered_entity or mouse.hovered_entity == floor:
            return
        if mouse.hovered_entity in spawned_objects:
            selected_object = mouse.hovered_entity
            update_info_text()
    elif key == 'delete' or key == 'backspace':
        delete_selected()
        
    if selected_object and selected_object in spawned_objects:
        move_speed = 1.0
        scale_speed = 1.0
        if held_keys['shift']:
            move_speed = 5.0
            scale_speed = 2.0
            
        if key == 'i': selected_object.z += move_speed
        if key == 'k': selected_object.z -= move_speed
        if key == 'j': selected_object.x -= move_speed
        if key == 'l': selected_object.x += move_speed
        if key == 'u': selected_object.y += move_speed
        if key == 'o': selected_object.y -= move_speed
        
        if key == 'up arrow': selected_object.scale_z += scale_speed
        if key == 'down arrow': selected_object.scale_z = max(1, selected_object.scale_z - scale_speed)
        if key == 'right arrow': selected_object.scale_x += scale_speed
        if key == 'left arrow': selected_object.scale_x = max(1, selected_object.scale_x - scale_speed)
        
        update_info_text()

def update():
    if selected_object and selected_object in spawned_objects:
        selection_indicator.position = selected_object.position
        selection_indicator.scale = selected_object.scale * 1.03

app.run()