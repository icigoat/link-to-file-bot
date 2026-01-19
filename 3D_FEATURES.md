# Interactive 3D Scene Features

## What's Included

### 🎨 3D Elements

#### 1. Floating Folder Icons (8 total)
- **Position**: Arranged in a circle around the scene
- **Material**: Glowing purple gradient with emissive lighting
- **Animation**: Gentle floating and rotation

#### 2. Particle System (200 particles)
- **Colors**: Gradient from blue to purple
- **Animation**: Rotating cloud effect
- **Blending**: Additive for glow effect

#### 3. Dynamic Lighting
- **Ambient Light**: Soft overall illumination
- **Point Lights**: Two colored lights (purple & pink) for depth

## 🎮 Interactive Features

### Mouse Movement
- **Camera Follow**: Camera smoothly follows mouse position
- **Parallax Effect**: Creates depth perception
- **Hover Detection**: Folders highlight when mouse hovers over them

### Hover Effects
- **Scale Up**: Folder grows to 1.3x size
- **Glow Increase**: Emissive intensity increases
- **Cursor Change**: Pointer cursor indicates interactivity
- **GSAP Animation**: Smooth elastic easing

### Click Interactions
- **Explosion Effect**: Folder shoots outward on click
- **Spin Animation**: 360° rotation on both axes
- **Return Animation**: Elastic bounce back to original position
- **Duration**: 0.5s out, 1s return with elastic easing

## 🎬 Animations

### Continuous Animations
1. **Particle Rotation**: Slow rotation on Y and X axes
2. **Folder Floating**: Sine wave vertical movement
3. **Folder Rotation**: Gentle Z-axis rotation
4. **Camera Movement**: Follows mouse position

### Triggered Animations (GSAP)
1. **Hover Scale**: `scale: 1.3` with `back.out` easing
2. **Hover Glow**: `emissiveIntensity: 0.8`
3. **Click Explosion**: Position multiplied by 2
4. **Click Spin**: `rotation += Math.PI * 2`
5. **Return**: `elastic.out` easing

## 🎯 Performance

### Optimizations
- **Particle Count**: 200 (balanced for mobile)
- **Folder Count**: 8 (optimal for interaction)
- **Render Loop**: RequestAnimationFrame (60fps)
- **Alpha Background**: Transparent for layering
- **Antialiasing**: Enabled for smooth edges

### Mobile Friendly
- **Touch Events**: Works with touch screens
- **Responsive**: Adapts to window resize
- **Pixel Ratio**: Matches device pixel ratio
- **Opacity**: 0.4 to not overwhelm content

## 🛠️ Customization

### Change Colors
```javascript
// Folder color
const bodyMaterial = new THREE.MeshPhongMaterial({
    color: 0x667eea,  // Change this hex color
    emissive: 0x667eea
});

// Light colors
const pointLight = new THREE.PointLight(0x667eea, 2);  // Purple
const pointLight2 = new THREE.PointLight(0x764ba2, 2); // Pink
```

### Adjust Animation Speed
```javascript
// Particle rotation speed
particles.rotation.y = time * 0.05;  // Increase for faster

// Folder floating speed
floatSpeed: Math.random() * 0.5 + 0.5  // Increase range

// Folder rotation speed
rotationSpeed: Math.random() * 0.02 - 0.01  // Increase range
```

### Change Folder Count
```javascript
const folderCount = 8;  // Increase or decrease
```

### Modify Hover Scale
```javascript
gsap.to(hoveredFolder.scale, {
    x: 1.3,  // Change scale factor
    y: 1.3,
    z: 1.3,
    duration: 0.3
});
```

## 🎨 Visual Effects

### Emissive Glow
- **Normal**: 0.2 intensity
- **Hover**: 0.8 intensity
- **Smooth Transition**: GSAP 0.3s

### Transparency
- **Folders**: 0.7 opacity
- **Particles**: 0.8 opacity
- **Background**: 0.4 opacity

### Blending
- **Particles**: Additive blending for glow
- **Folders**: Standard blending

## 📱 User Experience

### Visual Feedback
1. **Cursor Changes**: Pointer on hover
2. **Scale Animation**: Grows on hover
3. **Glow Effect**: Brightens on hover
4. **Explosion**: Satisfying click feedback

### Smooth Transitions
- All animations use GSAP for smooth easing
- Elastic and back easing for playful feel
- No jarring movements

## 🚀 Performance Tips

### For Better Performance
1. Reduce particle count to 100
2. Reduce folder count to 5
3. Lower emissive intensity
4. Disable antialiasing on mobile

### For Better Visuals
1. Increase particle count to 500
2. Add more lights
3. Increase emissive intensity
4. Add bloom post-processing

## 🎓 How It Works

### Scene Setup
1. Create Three.js scene, camera, renderer
2. Add particles and folders to scene
3. Setup lighting
4. Start animation loop

### Animation Loop
1. Update time-based animations
2. Rotate particles
3. Float folders
4. Render scene
5. Request next frame

### Interaction
1. Track mouse position
2. Update camera position
3. Raycast to detect hover
4. Apply GSAP animations
5. Handle click events

---

**Enjoy your interactive 3D background! 🎨✨**
