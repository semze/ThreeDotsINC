from ursina import *
from direct.actor.Actor import Actor

app = Ursina()
window.color = color.rgb(10, 10, 20)

fps_text = Text(text='State: -- | Timer: --', position=(-0.85, 0.45), scale=1.2, color=color.yellow)

class PlayerTest(Entity):
    def __init__(self):
        super().__init__()
        self.actor = Actor('player_model.gltf')
        self.actor.reparent_to(self)
        
        texture_mapping = {
            '**/armor': 'textures/armor.png',
            '**/head': 'textures/head.png',
            '**/sphere': 'textures/head.png',
            '**/hands': 'textures/hands.png',
            '**/grip': 'textures/gun.png'
        }
        for node_path, tex_path in texture_mapping.items():
            part = self.actor.find(node_path)
            if not part.is_empty():
                part.set_texture(loader.load_texture(tex_path), 1)

        # Define the states, their animations, and durations (10 seconds each)
        self.schedule = [
            ('idle', 10.0),
            ('walk', 10.0),
            ('run', 10.0)
        ]
        
        self.current_index = 0
        self.timer = 0.0
        self.start_current_state()

    def start_current_state(self):
        anim_name, duration = self.schedule[self.current_index]
        print(f"[+] Switching to '{anim_name}' for {duration} seconds")
        self.actor.loop(anim_name)
        self.timer = duration

    def update_timer(self):
        self.timer -= time.dt
        if self.timer <= 0:
            # Move to next state in sequence, loop back to start if at the end
            self.current_index = (self.current_index + 1) % len(self.schedule)
            self.start_current_state()

player = PlayerTest()

def update():
    player.update_timer()
    anim_name = player.schedule[player.current_index][0]
    fps_text.text = f'FPS: {int(1/time.dt)} | Anim: {anim_name} | Time Left: {max(0.0, player.timer):.1f}s'

EditorCamera()
app.run()