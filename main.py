import math
import json
import os
import time
import random
import socket
import threading
import queue
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageDraw

from panda3d.core import loadPrcFileData, TransparencyAttrib, WindowProperties
loadPrcFileData("", "interpolate-frames 1")
loadPrcFileData("", "want-shadows #t")
loadPrcFileData("", "shadow-map-size 4096")

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from ursina.shaders import lit_with_shadows_shader
from direct.actor.Actor import Actor

app = Ursina(development_mode=False)

# --- BORDERLESS WINDOWED FULLSCREEN SETUP ---

from panda3d.core import WindowProperties
props = WindowProperties()
props.setUndecorated(True)
props.setOrigin(0, 0)
props.setSize(1920, 1080)
base.win.requestProperties(props)


window.fullscreen = False
window.borderless = True
window.size = (1920, 1040)  # Slightly reduced height to stay above the Windows taskbar
window.position = (0, 0)
window.exit_button.visible = False
window.color = color.rgb(2, 2, 8)

# --- PROCEDURAL VIBRANT LASER-TAG GRID TEXTURE ---
grid_img_path = 'textures/procedural_grid_texture.png'
if not os.path.exists(grid_img_path):
    img = Image.new('RGB', (256, 256), (10, 14, 28))
    draw = ImageDraw.Draw(img)
    for i in range(0, 257, 64):
        draw.line([(i, 0), (i, 256)], fill=(0, 220, 255), width=8)
        draw.line([(0, i), (256, i)], fill=(0, 220, 255), width=8)
    img.save(grid_img_path)

# --- ADVANCED CYBER LIGHTING & SHADOW SETUP ---
try:
    skybox = Sky(texture='textures/ferndale_studio_12_1k.hdr')
except Exception:
    pass

sun = DirectionalLight(shadows=True, color=color.rgb(255, 255, 255))
sun.look_at(Vec3(1, -2, -0.8))
sun.intensity = 2.4

try:
    d_node = sun.node()
    d_node.setShadowMap(4096, 4096, 0)
    lens = d_node.getLens()
    lens.setFilmSize(80, 80) 
    lens.setNearFar(1, 200)
except Exception:
    pass

ambient = AmbientLight(color=color.rgb(15, 20, 35))

light_cyan = PointLight(parent=scene, position=(-15, 10, 15), color=color.rgb(0, 180, 255))
light_cyan.intensity = 2.0

light_pink = PointLight(parent=scene, position=(15, 10, 15), color=color.rgb(0, 100, 220))
light_pink.intensity = 1.5

# --- PLAYER & CONFIG SETUP ---
my_id = str(random.randint(10000, 99999))
spawn_x = ((int(my_id) % 9) - 4) * 3
spawn_z = (((int(my_id) // 9) % 9) - 4) * 3

selected_character = "red"  # Default character choice

player = FirstPersonController(x=spawn_x, y=100, z=spawn_z, origin_y=-.5)
player.cursor.visible = True

normal_speed = 7
sprint_speed = 15
crouch_speed = 5.5
player.speed = normal_speed

default_mouse_sens_x = player.mouse_sensitivity[0] if hasattr(player, 'mouse_sensitivity') else 40
default_mouse_sens_y = player.mouse_sensitivity[1] if hasattr(player, 'mouse_sensitivity') else 40

local_health = 100
max_local_health = 100
local_is_dead = False
last_shot_time = 0  
bullet_counter = 0
last_menu_close_time = 0

# --- HUD & HURT EFFECT SETUP ---
bar_bg = Entity(
    parent=camera.ui,
    model='quad',
    texture='textures/health_bar/health_background.png',
    color=color.white,
    scale=(0.35, 0.035),
    position=(-0.65, -0.42),
    unlit=True
)

bar_fill = Entity(
    parent=bar_bg,
    model='quad',
    texture='textures/health_bar/health_texture.png',
    color=color.white,
    scale=(0.98, 0.65),
    position=(-0.48, 0, -0.01),
    origin=(-0.5, 0),
    unlit=True
)

health_text = Text(
    parent=bar_bg,
    text="HP: 100/100",
    position=(-0.48, 1.2),
    scale=1.1,
    color=color.rgb(0, 180, 255)
)

hurt_overlay = Entity(
    parent=camera.ui,
    model='quad',
    texture='white_cube',
    color=color.rgba(255, 0, 0, 0),
    scale=(3.0, 3.0),
    z=2,
    unlit=True
)

def update_hud_health(current, maximum):
    ratio = max(0.0, min(1.0, current / maximum))
    bar_fill.scale_x = ratio * 0.98
    health_text.text = f"HP: {int(current)}/{int(maximum)}"
    if ratio < 0.3:
        bar_fill.color = color.rgb(255, 50, 50)
        health_text.color = color.rgb(255, 50, 50)
    else:
        bar_fill.color = color.white
        health_text.color = color.rgb(0, 180, 255)

def trigger_hurt_vignette():
    hurt_overlay.animate_color(color.rgba(255, 0, 0, 130), duration=0.0)
    hurt_overlay.animate_color(color.rgba(255, 0, 0, 0), duration=0.4, curve=curve.out_expo)

# --- AUDIO SETUP ---
try:
    walk_audio = Audio('audio/walking.mp3', loop=True, autoplay=True, volume=0)
    run_audio = Audio('audio/running.mp3', loop=True, autoplay=True, volume=0)
    mouse_friction_audio = Audio('audio/friction.mp3', loop=True, autoplay=True, volume=0)
except Exception:
    walk_audio = None
    run_audio = None
    mouse_friction_audio = None

# --- BLOCKBENCH MODEL VIEWMODEL ---
try:
    gun = Entity(
        model='textures/viewports/player_gun',
        shader=lit_with_shadows_shader,
        scale=0.5,
        position=(0.10, -0.25, -1),
        rotation=(0, 0, 0),
        parent=player.camera_pivot
    )
except Exception:
    gun = Entity(
        parent=player.camera_pivot,
        model='cube',
        color=color.rgb(0, 100, 200),
        scale=(0.3, 0.2, 0.8),
        position=(0.25, -0.45, 0.7)
    )

gun.is_firing = False

muzzle_parts = []
for _ in range(4):
    part = Entity(
        parent=gun,
        model='quad',
        color=color.rgba(0, 180, 255, 100),
        scale=(random.uniform(0.08, 0.18), random.uniform(0.08, 0.18), 1),
        position=(random.uniform(-0.02, 0.02), random.uniform(0.35, 0.45), random.uniform(0.35, 0.45)),
        enabled=False,
        unlit=True
    )
    muzzle_parts.append(part)

loaded_entities = []
targets = []
active_projectiles = []
remote_players = {}
packet_queue = queue.Queue()
is_firing_local = False
is_sprinting_global = False

class AnimatedCharacter(Entity):
    def __init__(self, player_id, char_type="red", **kwargs):
        super().__init__(**kwargs)
        self.player_id = player_id
        self.char_type = char_type
        
        self.collider = BoxCollider(self, center=Vec3(0, 1.0, 0), size=Vec3(1, 2.0, 1))
        self.collider.visible = False 
        
        self.max_health = 100
        self.health = self.max_health
        self.is_dead = False
        self.current_anim = ""
        self.last_firing_state = False
        self.target_pos = self.position
        self.target_rot = 0
        self.actor = None
        
        try:
            folder = f"textures/{self.char_type}_player"
            model_path = f"{folder}/{self.char_type}_model.gltf"
            
            self.actor = Actor(model_path)
            self.actor.reparent_to(self)
            self.actor.clear_color()
            self.actor.set_blend(frameBlend=True)
            
            armor_filename = 'armor (3).png' if self.char_type == 'red' else 'armor.png'
            
            textures_map = {
                '**/armor': f'{folder}/{armor_filename}',
                '**/head': f'{folder}/head.png',
                '**/hands': f'{folder}/hands.png',
                '**/sphere': f'{folder}/head.png',
                '**/grip': f'{folder}/gun.png'
            }
            
            if self.char_type == 'white':
                textures_map['**/backpack'] = f'{folder}/backpack.png'
            
            for node_query, tex_path in textures_map.items():
                part_node = self.actor.find(node_query)
                if not part_node.is_empty():
                    if os.path.exists(tex_path):
                        tex = loader.load_texture(tex_path)
                        if tex:
                            part_node.set_texture(tex, 1)

            head_mesh = self.actor.find("**/sphere")
            if not head_mesh.is_empty():
                head_mesh.reparent_to(self.actor)

            gun_mesh = self.actor.find("**/grip")
            if not gun_mesh.is_empty():
                gun_mesh.reparent_to(self.actor)
            
            self.set_anim_state(is_moving=False, is_sprinting=False)
            
        except Exception:
            fallback_cols = {
                "blue": color.rgb(50, 150, 255),
                "green": color.rgb(50, 255, 50),
                "purple": color.rgb(180, 50, 255),
                "black": color.rgb(30, 30, 30),
                "white": color.rgb(230, 230, 230)
            }
            fallback_col = fallback_cols.get(self.char_type, color.rgb(255, 50, 50))

            self.fallback_visual = Entity(
                parent=self,
                model='cube',
                color=fallback_col,
                scale=(1, 2, 1),
                position=(0, 1, 0),
                unlit=True
            )

    def set_anim_state(self, is_moving, is_sprinting):
        if self.is_dead: 
            return
            
        desired_anim = 'idle'
        if is_moving:
            desired_anim = 'run' if is_sprinting else 'walk'
            
        if self.current_anim != desired_anim:
            self.current_anim = desired_anim
            if self.actor and hasattr(self.actor, 'get_anim_names') and desired_anim in self.actor.get_anim_names():
                try:
                    self.actor.loop(desired_anim)
                except Exception:
                    pass

    def take_damage(self, amount, shooter_id="unknown"):
        if self.is_dead:
            return
        self.health -= amount
        try:
            if self.actor:
                self.actor.setColorScale(Vec4(2, 0.5, 0.5, 1))
                invoke(self.actor.clearColorScale, delay=0.15)
        except Exception:
            pass
        if self.health <= 0:
            self.die()

    def die(self):
        if self.is_dead:
            return
        self.is_dead = True
        self.health = 0
        self.enabled = False
        if self.collider:
            self.collider.enabled = False
        try:
            if self.actor:
                self.actor.stop()
            if hasattr(self, 'fallback_visual') and self.fallback_visual:
                self.fallback_visual.enabled = False
        except Exception:
            pass
        invoke(self.respawn, delay=3.0)

    def respawn(self):
        self.health = self.max_health
        self.is_dead = False
        self.enabled = True
        if self.collider:
            self.collider.enabled = True
        if hasattr(self, 'fallback_visual') and self.fallback_visual:
            self.fallback_visual.enabled = True
        self.position = (spawn_x, 100, spawn_z)
        self.target_pos = self.position

def load_json_map(filename):
    global loaded_entities, targets
    for e in loaded_entities[:]:
        if e:
            try:
                destroy(e)
            except Exception:
                pass
    loaded_entities.clear()
    targets.clear()
    
    floor = Entity(
        model='cube',
        position=(0, -1, 0),
        scale=(300, 2, 300),
        color=color.rgb(40, 48, 70),
        texture=grid_img_path,
        texture_scale=(100, 100),
        shader=lit_with_shadows_shader,
        collider='box'
    )
    floor.tag = "ground"
    loaded_entities.append(floor)

    try:
        with open(filename, "r") as f:
            map_data = json.load(f)
            
        for data in map_data:
            col_vals = data.get("color", [1, 1, 1, 1])
            col = color.Color(col_vals[0], col_vals[1], col_vals[2], col_vals[3])
            
            model_type = data.get("model", "cube")
            scale_x = data["scale"][0]
            scale_y = data["scale"][1]
            scale_z = data["scale"][2]
            tag = data.get("tag", "prop")

            try:
                e = Entity(
                    model=model_type,
                    position=Vec3(data["position"][0], data["position"][1], data["position"][2]),
                    scale=Vec3(scale_x, scale_y, scale_z),
                    color=col,
                    shader=lit_with_shadows_shader
                )
            except Exception as model_err:
                print(f"Failed to load model '{model_type}': {model_err}")
                continue
            
            if model_type == "cube":
                e.texture = grid_img_path
                e.texture_scale = (max(scale_x, scale_z) / 4.0, max(scale_y, scale_z) / 4.0)
                e.collider = 'box'
            else:
                e.collider = None
                if hasattr(e, 'findAllMatches'):
                    hitboxes = e.findAllMatches("**/=hitbox*") or e.findAllMatches("**/*hitbox*")
                    for path_node in hitboxes:
                        child_ent = Entity(parent=e, node=path_node)
                        child_ent.collider = BoxCollider(child_ent)
                        child_ent.color = color.rgba(0, 0, 0, 0)
                        child_ent.alpha = 0
                        path_node.set_color_scale(0, 0, 0, 0)
            
            e.tag = tag
            loaded_entities.append(e)
            
            if e.tag == "target":
                targets.append(e)
                
    except Exception as ex:
        print(f"Error loading map json: {ex}")

# Load map from the new maps folder
load_json_map("maps/my_custom_map.json")

# --- STARTUP INTRO VIDEO OVERLAY ---
startup_video = Entity(
    parent=camera.ui,
    model='quad',
    color=color.white,
    scale=(2.0, 2.0),
    z=-2,
    enabled=os.path.exists('media/startup.mp4'),
    unlit=True
)

if startup_video.enabled:
    try:
        startup_video.texture = 'media/startup.mp4'
        if hasattr(startup_video.texture, 'setLoop'):
            startup_video.texture.setLoop(False)
        if hasattr(startup_video.texture, 'play'):
            startup_video.texture.play()
    except Exception:
        pass

# --- STARTUP INTRO AUDIO ---
startup_audio_delay = 0.0

def play_startup_audio():
    try:
        if os.path.exists('audio/presents.mp3'):
            Audio('audio/presents.mp3', autoplay=True, volume=1.0, loop=False)
    except Exception:
        pass

if startup_audio_delay <= 0:
    play_startup_audio()
else:
    invoke(play_startup_audio, delay=startup_audio_delay)

def finish_startup_intro():
    if startup_video.enabled:
        startup_video.animate_color(color.rgba(1, 1, 1, 0), duration=0.5)
        def disable_intro():
            startup_video.enabled = False
        invoke(disable_intro, delay=1.0)

invoke(finish_startup_intro, delay=5.0)

# --- VIDEO BACKGROUND & UI SETUP ---
menu_video_filename = 'media/background.mp4'

menu_background = Entity(
    parent=camera.ui,
    model='quad',
    texture=menu_video_filename if os.path.exists(menu_video_filename) else 'white_cube',
    color=color.white,
    scale=(1.1, 0.8),
    z=1,
    enabled=False,
    unlit=True
)

if menu_background.texture and hasattr(menu_background.texture, 'play'):
    try:
        menu_background.texture.play()
        if hasattr(menu_background.texture, 'setLoop'):
            menu_background.texture.setLoop(True)
    except Exception:
        pass

menu_title = Text(parent=menu_background, text="THREE·DOTS // PAUSE MENU", position=(-0.42, 0.42), scale=1.2, color=color.rgb(0, 230, 255), z=-0.05)
Entity(parent=menu_background, model='quad', color=color.rgba(0, 230, 255, 80), scale=(0.92, 0.003), position=(0, 0.34), unlit=True, texture='white_cube', z=-0.03)

status_text = Text(parent=menu_background, text="STATUS: SYSTEM READY", position=(-0.42, 0.26), scale=0.65, color=color.rgb(0, 180, 255), z=-0.05)

menu_open = False

def toggle_menu():
    global menu_open, last_menu_close_time
    menu_open = not menu_open
    menu_background.enabled = menu_open
    for btn in menu_buttons:
        btn.enabled = menu_open
        
    if menu_open:
        try:
            if os.path.exists('audio/open_esc.mp3'):
                Audio('audio/open_esc.mp3', autoplay=True, volume=0.8)
        except Exception:
            pass
        mouse.locked = False
        player.cursor.visible = True
        player.mouse_sensitivity = Vec2(0, 0)
        if menu_background.texture and hasattr(menu_background.texture, 'play'):
            try:
                menu_background.texture.play()
            except Exception:
                pass
    else:
        try:
            if os.path.exists('audio/close_esc.mp3'):
                Audio('audio/close_esc.mp3', autoplay=True, volume=0.8)
        except Exception:
            pass
        mouse.locked = True
        player.cursor.visible = True
        player.mouse_sensitivity = Vec2(default_mouse_sens_x, default_mouse_sens_y)
        if hasattr(mouse, 'x'):
            mouse.x = 0
            mouse.y = 0
        last_menu_close_time = time.time()

def play_hover_sound():
    try:
        if os.path.exists('audio/hover.wav'):
            Audio('audio/hover.wav', autoplay=True, volume=0.5)
    except Exception:
        pass

def play_click_sound():
    try:
        if os.path.exists('audio/click.wav'):
            Audio('audio/click.wav', autoplay=True, volume=0.7)
    except Exception:
        pass

def toggle_character_choice():
    play_click_sound()
    global selected_character
    if selected_character == "red":
        selected_character = "green"
        char_btn.text = "[ ACTIVE CLASS: VEX-7 (GREEN) ]"
        char_btn.text_color = color.rgb(50, 255, 100)
    elif selected_character == "green":
        selected_character = "blue"
        char_btn.text = "[ ACTIVE CLASS: KRIX-9 (BLUE) ]"
        char_btn.text_color = color.rgb(50, 180, 255)
    elif selected_character == "blue":
        selected_character = "purple"
        char_btn.text = "[ ACTIVE CLASS: NYX-5 (PURPLE) ]"
        char_btn.text_color = color.rgb(200, 80, 255)
    elif selected_character == "purple":
        selected_character = "black"
        char_btn.text = "[ ACTIVE CLASS: UMBRA-X (BLACK) ]"
        char_btn.text_color = color.rgb(150, 150, 150)
    elif selected_character == "black":
        selected_character = "white"
        char_btn.text = "[ ACTIVE CLASS: ZEPHYR (WHITE) ]"
        char_btn.text_color = color.rgb(240, 240, 240)
    else:
        selected_character = "red"
        char_btn.text = "[ ACTIVE CLASS: SYN-0 (RED) ]"
        char_btn.text_color = color.rgb(255, 80, 80)

def reload_map_action():
    play_click_sound()
    load_json_map("maps/my_custom_map.json")

def join_server_action():
    play_click_sound()
    status_text.text = "STATUS: LINK ESTABLISHED"
    status_text.color = color.rgb(50, 255, 100)
    toggle_menu()
    start_client()

def resume_action():
    play_click_sound()
    toggle_menu()

def quit_action():
    play_click_sound()
    application.quit()

class CyberButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.texture = None
        self._was_hovered = False

    def update(self):
        if self.enabled and self.hovered and not self._was_hovered:
            play_hover_sound()
        self._was_hovered = self.hovered if self.enabled else False

char_btn = CyberButton(
    parent=menu_background, text="[ ACTIVE CLASS: SYN-0 (RED) ]", position=(0, 0.12),
    scale=(0.88, 0.08), z=-0.05, color=color.clear,
    highlight_color=color.rgba(0, 120, 240, 60), pressed_color=color.rgba(0, 80, 160, 100),
    text_color=color.rgb(255, 80, 80), on_click=toggle_character_choice
)
map_btn = CyberButton(
    parent=menu_background, text="[ RELOAD MAP ]", position=(0, 0.02),
    scale=(0.88, 0.08), z=-0.05, color=color.clear,
    highlight_color=color.rgba(0, 120, 240, 60), pressed_color=color.rgba(0, 80, 160, 100),
    text_color=color.rgb(0, 230, 255), on_click=reload_map_action
)
join_btn = CyberButton(
    parent=menu_background, text="[ JOIN SERVER ]", position=(0, -0.08),
    scale=(0.88, 0.08), z=-0.05, color=color.clear,
    highlight_color=color.rgba(0, 120, 240, 60), pressed_color=color.rgba(0, 80, 160, 100),
    text_color=color.rgb(0, 230, 255), on_click=join_server_action
)
resume_btn = CyberButton(
    parent=menu_background, text="[ RESUME GAME ]", position=(0, -0.18),
    scale=(0.88, 0.08), z=-0.05, color=color.clear,
    highlight_color=color.rgba(0, 120, 240, 60), pressed_color=color.rgba(0, 80, 160, 100),
    text_color=color.rgb(180, 230, 255), on_click=resume_action
)
quit_btn = CyberButton(
    parent=menu_background, text="[ QUIT APPLICATION ]", position=(0, -0.28),
    scale=(0.88, 0.08), z=-0.05, color=color.clear,
    highlight_color=color.rgba(0, 120, 240, 60), pressed_color=color.rgba(0, 80, 160, 100),
    text_color=color.rgb(255, 65, 65), on_click=quit_action
)

menu_buttons = [char_btn, map_btn, join_btn, resume_btn, quit_btn]
for btn in menu_buttons:
    btn.enabled = False

# --- NETWORKING CLIENT ARCHITECTURE ---
is_networking = False
conn_socket = None

def send_network_packet(packet_dict):
    global conn_socket
    if conn_socket:
        try:
            raw = json.dumps(packet_dict) + '\n'
            conn_socket.sendall(raw.encode())
        except Exception:
            pass

def respawn_local_player():
    global local_health, local_is_dead
    local_health = max_local_health
    local_is_dead = False
    player.x, player.y, player.z = spawn_x, 100, spawn_z
    player.enabled = True
    player.speed = normal_speed
    update_hud_health(local_health, max_local_health)
    hurt_overlay.animate_color(color.rgba(255, 0, 0, 0), duration=0.0)

def get_local_player_packet():
    is_moving = (held_keys['w'] or held_keys['a'] or held_keys['s'] or held_keys['d']) and player.grounded
    return {
        "type": "pos",
        "id": my_id,
        "character": selected_character,
        "x": player.x,
        "y": player.y,
        "z": player.z,
        "rot": player.rotation_y,
        "grounded": player.grounded,
        "moving": is_moving,
        "sprinting": is_sprinting_global,
        "firing": is_firing_local
    }

def start_client():
    global conn_socket, is_networking
    if conn_socket: 
        return
    
    is_networking = True
    conn_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        conn_socket.connect(('127.0.0.1', 55555)) 
        threading.Thread(target=client_receive_loop, daemon=True).start()
    except Exception:
        conn_socket = None
        is_networking = False

def client_receive_loop():
    try:
        rfile = conn_socket.makefile('r')
        while True:
            if not conn_socket:
                break
            
            packet = get_local_player_packet()
            conn_socket.sendall((json.dumps(packet) + '\n').encode())
            
            line = rfile.readline()
            if not line: break
            server_packet = json.loads(line.strip())
            
            if server_packet.get('id') != my_id:
                packet_queue.put(server_packet)
                
            time.sleep(0.015)
    except Exception:
        pass

def process_network_packets():
    global local_health, local_is_dead
    while not packet_queue.empty():
        if packet_queue.qsize() > 30:
            try:
                packet_queue.get_nowait()
                continue
            except queue.Empty:
                break
                
        try:
            packet = packet_queue.get_nowait()
            p_type = packet.get('type', 'pos')
            
            if p_type == 'hit':
                target_id = packet.get('target_id')
                sender_id = packet.get('id')
                dmg = packet.get('damage', 25)
                b_id = packet.get('bullet_id', '')
                
                if sender_id == my_id or str(b_id).startswith(str(my_id) + "_"):
                    continue

                if target_id == my_id:
                    if not local_is_dead:
                        local_health -= dmg
                        trigger_hurt_vignette()
                        update_hud_health(local_health, max_local_health)
                        if local_health <= 0:
                            local_is_dead = True
                            local_health = 0
                            player.speed = 0
                            invoke(respawn_local_player, delay=3.0)
                            send_network_packet({"type": "death", "id": my_id})
                elif target_id in remote_players:
                    remote_players[target_id].take_damage(dmg, shooter_id=sender_id)
            elif p_type == 'death':
                target_id = packet.get('id')
                if target_id in remote_players:
                    remote_players[target_id].die()
            elif p_type == 'respawn':
                target_id = packet.get('id')
                if target_id in remote_players:
                    remote_players[target_id].respawn()
            else:
                p_id = packet.get('id')
                if p_id and p_id != my_id:
                    update_remote_player(p_id, packet)
        except queue.Empty:
            break

def update_remote_player(p_id, data):
    char_type = data.get("character", "red")
    if p_id not in remote_players:
        try:
            rp = AnimatedCharacter(p_id, char_type=char_type, position=(data["x"], data["y"], data["z"]))
            remote_players[p_id] = rp
        except Exception:
            return
    
    rp = remote_players[p_id]
    if rp and not rp.is_dead:
        rp.target_pos = Vec3(data["x"], data["y"], data["z"])
        rp.target_rot = data["rot"]
        rp.set_anim_state(data.get("moving", False), data.get("sprinting", False))
        
        is_firing_remote = data.get("firing", False)
        if is_firing_remote and not rp.last_firing_state:
            spawn_visual_bullet(Vec3(data["x"], data["y"] + 1.8, data["z"]), data["rot"], shooter_id=p_id)
        rp.last_firing_state = is_firing_remote

def spawn_visual_bullet(start_pos, rot_y, shooter_id):
    global bullet_counter
    bullet_counter += 1
    b_id = f"{shooter_id}_{bullet_counter}"
    
    rad = math.radians(rot_y)
    forward_dir = Vec3(math.sin(rad), 0, math.cos(rad))
    bullet = Entity(
        model='sphere',
        color=color.rgb(255, 100, 0),
        scale=0.1,
        position=start_pos,
        unlit=True
    )
    bullet.shooter_id = shooter_id
    bullet.bullet_id = b_id
    bullet.direction = forward_dir
    bullet.velocity = bullet.direction * 250
    bullet.life_time = 1.5
    active_projectiles.append(bullet)

# --- WEAPON & GAMEPLAY VARS ---
bob_timer = 0
current_cam_y = 0
fire_delay = 0.50 
was_grounded = True
was_crouching = False
was_aiming = False
jump_offset = 0
recoil_shake = 0
cam_recoil = 0 
last_friction_sound = 0 

def play_random_friction_snippet(volume=0.4, pitch=1.1):
    global last_friction_sound
    if time.time() - last_friction_sound > 0.4:
        try:
            snd = Audio('audio/friction.mp3', autoplay=True, volume=volume, pitch=pitch)
            try:
                snd.time = random.uniform(0.0, 1.5)
            except:
                pass
            
            def cut_sound():
                try:
                    snd.stop()
                    destroy(snd)
                except:
                    pass
            invoke(cut_sound, delay=0.5)
            last_friction_sound = time.time()
        except Exception:
            pass

def shoot(target_pos):
    global last_shot_time, recoil_shake, cam_recoil, is_firing_local, bullet_counter
    last_shot_time = time.time()
    gun.is_firing = True
    is_firing_local = True
    
    bullet_counter += 1
    b_id = f"{my_id}_{bullet_counter}"
    
    try:
        Audio('audio/fire.mp3', autoplay=True, volume=0.65, pitch=random.uniform(0.95, 1.05))
    except Exception:
        pass
    
    for part in muzzle_parts:
        part.enabled = True
        part.rotation_z = random.randint(0, 180)
        part.rotation_y = random.randint(0, 45)
    
    def hide_flash():
        for part in muzzle_parts:
            part.enabled = False
        global is_firing_local
        is_firing_local = False
    invoke(hide_flash, delay=0.15)
    
    muzzle_world_pos = gun.world_position + (gun.forward * 6.5) + (gun.up * 0.15)
    
    bullet = Entity(
        model='sphere',
        color=color.rgb(0, 200, 255),
        scale=0.1,
        position=muzzle_world_pos,
        shader=lit_with_shadows_shader,
        collider='sphere',
        unlit=True
    )
    bullet.shooter_id = my_id
    bullet.bullet_id = b_id
    
    aim_target = camera.world_position + (camera.forward * 100)
    bullet.direction = (aim_target - muzzle_world_pos).normalized()
    bullet.velocity = bullet.direction * 250
    bullet.gravity = -0.4 
    bullet.life_time = 2.0 
    active_projectiles.append(bullet)
    
    send_network_packet(get_local_player_packet())
    
    recoil_mult = 0.4 if held_keys['right mouse'] else 1.0
    
    gun.position = target_pos + Vec3(random.uniform(-0.02, 0.02), 0.08 * recoil_mult, -0.16 * recoil_mult)
    gun.rotation = Vec3(-15 * recoil_mult, random.uniform(-3, 3), random.uniform(-5, 5))
    
    cam_recoil += 2.2 * recoil_mult
    recoil_shake = 0.06 * recoil_mult 
    
    def reset_gun():
        gun.animate_position(target_pos, duration=0.06, curve=curve.out_bounce)
        gun.animate_rotation(Vec3(0, 0, 0), duration=0.06, curve=curve.out_bounce)
        
        def unlock_firing():
            gun.is_firing = False
        invoke(unlock_firing, delay=0.06)
        
    invoke(reset_gun, delay=0.03)

def update():
    global bob_timer, current_cam_y, was_grounded, was_crouching, was_aiming, jump_offset, recoil_shake, cam_recoil, is_sprinting_global

    dt = min(time.dt, 0.1)

    process_network_packets()

    for rp_id, rp in list(remote_players.items()):
        if rp and hasattr(rp, 'target_pos') and not rp.is_dead:
            if rp.position is not None and rp.target_pos is not None:
                rp.position = lerp(rp.position, rp.target_pos, dt * 18)
                cur_rot = rp.rotation_y if rp.rotation_y is not None else 0
                rp.rotation_y = lerp(cur_rot, rp.target_rot if rp.target_rot is not None else 0, dt * 18)

    if menu_open or local_is_dead:
        player.mouse_sensitivity = Vec2(0, 0)
        if walk_audio: walk_audio.volume = 0
        if run_audio: run_audio.volume = 0
        if mouse_friction_audio: mouse_friction_audio.volume = 0
        return

    mouse_speed = mouse.velocity.length() if hasattr(mouse, 'velocity') else 0

    for b in active_projectiles[:]:
        if not b or not hasattr(b, 'position') or not b.enabled:
            if b in active_projectiles:
                active_projectiles.remove(b)
            continue

        if hasattr(b, 'gravity') and b.gravity:
            b.velocity.y += b.gravity * dt
        movement = b.velocity * dt
        
        ignore_list = [player, b, gun]
        if hasattr(player, 'collider') and player.collider:
            ignore_list.append(player.collider)
        if hasattr(player, 'camera_pivot'):
            ignore_list.append(player.camera_pivot)
        for child in player.children:
            ignore_list.append(child)
            
        hit = raycast(b.position, b.velocity.normalized(), distance=movement.length(), ignore=ignore_list)
        
        if hit.hit:
            b_id = getattr(b, 'bullet_id', '')
            s_id = getattr(b, 'shooter_id', '')
            
            if s_id != my_id:
                destroy(b)
                if b in active_projectiles:
                    active_projectiles.remove(b)
                continue

            if s_id == my_id:
                if (hit.entity is player or
                    hit.entity in player.children or
                    hit.entity is gun or
                    (hasattr(player, 'collider') and hit.entity is player.collider) or
                    (hasattr(player, 'camera_pivot') and hit.entity is player.camera_pivot) or
                    (hasattr(hit.entity, 'parent') and (hit.entity.parent is player or hit.entity.parent is gun))):
                    b.position += b.velocity.normalized() * 0.8
                    continue

            hit_something = False
            for rp_id, rp in remote_players.items():
                if rp and not rp.is_dead and (hit.entity is rp or hit.entity is getattr(rp, 'collider', None)):
                    rp.take_damage(25, shooter_id=s_id)
                    send_network_packet({
                        "type": "hit",
                        "id": my_id,
                        "target_id": rp_id,
                        "damage": 25,
                        "bullet_id": b_id
                    })
                    if rp.is_dead:
                        send_network_packet({
                            "type": "death",
                            "id": rp_id
                        })
                    hit_something = True
                    break
            
            if not hit_something and hit.entity in targets:
                hit.entity.color = color.rgb(0, 255, 100)
                invoke(setattr, hit.entity, 'color', color.rgb(0, 255, 220), delay=0.2)
                hit_something = True
            
            if hit_something:
                destroy(b)
                if b in active_projectiles:
                    active_projectiles.remove(b)
        else:
            b.position += movement
            
        b.life_time -= dt
        if b.life_time <= 0:
            destroy(b)
            if b in active_projectiles:
                active_projectiles.remove(b)

    is_aiming = held_keys['right mouse']
    is_crouching = held_keys['control']
    is_sprinting = held_keys['shift'] and not is_crouching and not is_aiming
    is_sprinting_global = is_sprinting
    
    if is_aiming and not was_aiming:
        play_random_friction_snippet(volume=0.3, pitch=1.0)
    was_aiming = is_aiming

    if is_crouching and not was_crouching:
        play_random_friction_snippet(volume=0.4, pitch=1.3)
    was_crouching = is_crouching

    if not player.grounded and was_grounded:
        jump_offset = -0.06
        play_random_friction_snippet(volume=0.5, pitch=1.1)

    was_grounded = player.grounded

    if mouse_friction_audio:
        cur_vol = mouse_friction_audio.volume if mouse_friction_audio.volume is not None else 0.0
        if mouse_speed > 0.002 and not menu_open:
            target_vol = min(mouse_speed * 1.5, 0.25)
            mouse_friction_audio.volume = max(0.0, min(1.0, lerp(cur_vol, target_vol, dt * 15)))
        else:
            mouse_friction_audio.volume = max(0.0, min(1.0, lerp(cur_vol, 0.0, dt * 20)))

    if is_aiming:
        player.speed = normal_speed * 0.6
        target_base_y = 0
        target_gun_pos = Vec3(0.0005, -0.40, 0.8) 
        target_gun_rot = Vec3(0, 0, 0)
        target_fov = 40
        player.mouse_sensitivity = Vec2(default_mouse_sens_x * 0.45, default_mouse_sens_y * 0.45)
    else:
        player.mouse_sensitivity = Vec2(default_mouse_sens_x, default_mouse_sens_y)
        if is_crouching:
            player.speed = crouch_speed
            target_base_y = -0.5
            target_gun_pos = Vec3(0.25, -0.75, 0.7)
            target_gun_rot = Vec3(0, 0, 0)
            target_fov = 90
        elif is_sprinting:
            player.speed = sprint_speed
            target_base_y = 0
            target_gun_pos = Vec3(0.25, -0.45, 0.7)
            target_gun_rot = Vec3(0, 0, 0)
            target_fov = 120
        else:
            player.speed = normal_speed
            target_base_y = 0
            target_gun_pos = Vec3(0.25, -0.45, 0.7)
            target_gun_rot = Vec3(0, 0, 0)
            target_fov = 100

    cam_fov = camera.fov if camera.fov is not None else 90
    camera.fov = lerp(cam_fov, target_fov, dt * 22)
    current_cam_y = lerp(current_cam_y if current_cam_y is not None else 0, target_base_y, dt * 15)

    player.camera_pivot.rotation_x -= cam_recoil * dt * 14
    cam_recoil = lerp(cam_recoil, 0, dt * 12)
    recoil_shake = lerp(recoil_shake, 0, dt * 20)

    if player.grounded:
        jump_offset = lerp(jump_offset, 0, dt * 10)
    else:
        jump_offset = lerp(jump_offset, -0.03, dt * 5)

    can_shoot = (time.time() - last_menu_close_time > 0.2) and not local_is_dead
    if can_shoot and held_keys['left mouse'] and not gun.is_firing and (time.time() - last_shot_time >= fire_delay):
        shoot(target_gun_pos)

    is_moving = (held_keys['w'] or held_keys['a'] or held_keys['s'] or held_keys['d']) and player.grounded

    if walk_audio and run_audio:
        walk_vol = walk_audio.volume if walk_audio.volume is not None else 0.0
        run_vol = run_audio.volume if run_audio.volume is not None else 0.0
        if is_moving:
            if is_sprinting:
                run_audio.volume = max(0.0, min(1.0, lerp(run_vol, 1.0, dt * 12)))
                walk_audio.volume = max(0.0, min(1.0, lerp(walk_vol, 0.0, dt * 12)))
            else:
                walk_audio.volume = max(0.0, min(1.0, lerp(walk_vol, 1.0, dt * 12)))
                run_audio.volume = max(0.0, min(1.0, lerp(run_vol, 0.0, dt * 12)))
        else:
            walk_audio.volume = max(0.0, min(1.0, lerp(walk_vol, 0.0, dt * 12)))
            run_audio.volume = max(0.0, min(1.0, lerp(run_vol, 0.0, dt * 12)))

    if not gun.is_firing:
        if is_moving and not is_aiming:
            bob_freq = 15 if is_sprinting else (8 if is_crouching else 11)
            bob_amp = 0.05 if is_sprinting else (0.02 if is_crouching else 0.03)
            
            bob_timer += dt * bob_freq
            bob_offset = math.sin(bob_timer) * bob_amp
            
            camera.y = current_cam_y + bob_offset
            
            gun.position = Vec3(
                target_gun_pos.x + math.sin(bob_timer * 0.5) * 0.015,
                target_gun_pos.y + abs(math.sin(bob_timer)) * 0.02 + jump_offset,
                target_gun_pos.z
            )
        else:
            bob_timer = 0
            cam_y = camera.y if camera.y is not None else current_cam_y
            camera.y = lerp(cam_y, current_cam_y, dt * 15)
            shake_offset = Vec3(random.uniform(-recoil_shake, recoil_shake), random.uniform(-recoil_shake, recoil_shake), 0)
            final_pos = target_gun_pos + Vec3(0, jump_offset, 0) + shake_offset
            gun_pos = gun.position if gun.position is not None else final_pos
            gun_rot = gun.rotation if gun.rotation is not None else target_gun_rot
            gun.position = lerp(gun_pos, final_pos, dt * 25)
            gun.rotation = lerp(gun_rot, target_gun_rot, dt * 25)

def input(key):
    if key == 'escape':
        toggle_menu()

app.run()