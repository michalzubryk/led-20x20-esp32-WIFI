import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import validate_shape
from render import DEFAULT,render

class HalloweenTest(unittest.TestCase):
    def test_pack_and_animation_frames(self):
        shapes=json.loads((Path(__file__).resolve().parents[1]/'halloween/shapes.json').read_text())
        self.assertEqual(len(shapes),10)
        self.assertEqual(len({s['name'] for s in shapes}),10)
        self.assertEqual(sum(s['kind']=='animation' for s in shapes),3)
        for shape in shapes:
            with self.subTest(shape=shape['name']):
                validate_shape(shape)
                self.assertTrue(shape['name'].startswith('Halloween · '))
                frames=shape['frames']
                self.assertTrue(all(any(f) for f in frames))
                if shape['kind']=='animation':
                    self.assertGreater(len({bytes(f) for f in frames}),1)
                    config={**DEFAULT,'mode':'custom','shapeId':'test','direction':'none','brightness':255}
                    # Rendering loops the same motif and freezing chooses its first frame.
                    self.assertEqual(render(config,0,{'test':shape}),render(config,len(frames)*shape['durationMs']/1000,{'test':shape}))
                    self.assertEqual(render({**config,'animate':False},99,{'test':shape}),bytes(frames[0]))
