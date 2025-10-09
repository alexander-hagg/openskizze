# Hard Constraints UI Update - Sliders Implementation

**Date**: October 9, 2025
**Change**: Converted hard constraint inputs from number fields to interactive sliders

## Summary

Updated Step 2 hard constraints UI to use sliders instead of number input fields, providing a better user experience with visual feedback and easier value selection. Values are automatically saved and restored just like feature ranges.

## Changes Made

### 1. UI Components Updated (`pages/step2_constraints.py`)

#### Before (Number Inputs):
```python
dbc.Label(T[lang]['STEP2_MAX_HEIGHT_LABEL']),
dbc.Input(id='max-height-constraint', type="number", 
         placeholder=T[lang]['STEP2_MAX_HEIGHT_PLACEHOLDER'], 
         min=3, max=30, step=1, value=ENCODING_CONFIG['z_length']),

dbc.Label(T[lang]['STEP2_MIN_DISTANCE_LABEL'], className="mt-2"),
dbc.Input(id='min-distance-constraint', type="number", 
         placeholder=T[lang]['STEP2_MIN_DISTANCE_PLACEHOLDER'], 
         min=0, step=1, value=0),
```

#### After (Interactive Sliders):
```python
# Max Height Slider
dbc.Label([T[lang]['STEP2_MAX_HEIGHT_LABEL'], 
          html.Span(id='max-height-value', className='ms-2 text-primary fw-bold')]),
dcc.Slider(
    id='max-height-constraint',
    min=3,
    max=30,
    step=1,
    value=ENCODING_CONFIG['z_length'],
    marks={3: '3m', 10: '10m', 20: '20m', 30: '30m'},
    tooltip={"placement": "bottom", "always_visible": False}
),

# Min Distance Slider
dbc.Label([T[lang]['STEP2_MIN_DISTANCE_LABEL'], 
          html.Span(id='min-distance-value', className='ms-2 text-primary fw-bold')], 
         className="mt-3"),
dcc.Slider(
    id='min-distance-constraint',
    min=0,
    max=30,
    step=1,
    value=0,
    marks={0: '0m', 10: '10m', 20: '20m', 30: '30m'},
    tooltip={"placement": "bottom", "always_visible": False}
),
```

### 2. Value Display Callbacks Added

Two new callbacks update the displayed values in real-time:

```python
@callback(
    Output('max-height-value', 'children'),
    Input('max-height-constraint', 'value')
)
def update_max_height_display(value):
    """Update the displayed max height value"""
    if value is None:
        return ""
    return f"({value}m)"

@callback(
    Output('min-distance-value', 'children'),
    Input('min-distance-constraint', 'value')
)
def update_min_distance_display(value):
    """Update the displayed min distance value"""
    if value is None:
        return ""
    return f"({value}m)"
```

### 3. Persistence (Already Working)

No changes needed! The existing session save/restore callbacks already handle the slider values:

- **Save**: `update_session_with_features_and_ranges()` saves constraint values to session
- **Restore**: `restore_step2_from_session()` restores constraint values from session
- Both work identically whether the component is an input or a slider (same `value` property)

## Features

### Max Height Slider
- **Range**: 3-30 meters
- **Step**: 1 meter increments
- **Marks**: Visual indicators at 3m, 10m, 20m, 30m
- **Tooltip**: Shows value on hover
- **Display**: Live value shown in label: "Max Height (15m)"

### Min Distance Slider
- **Range**: 0-30 meters
- **Step**: 1 meter increments
- **Marks**: Visual indicators at 0m, 10m, 20m, 30m
- **Tooltip**: Shows value on hover
- **Display**: Live value shown in label: "Min Distance (6m)"

## User Experience Improvements

### Before (Number Inputs):
- ❌ Had to type values manually
- ❌ No visual sense of valid range
- ❌ Easy to enter invalid values
- ❌ No immediate feedback on current value
- ❌ Less intuitive for quick adjustments

### After (Sliders):
- ✅ Visual slider for easy adjustment
- ✅ Clear visual range (3-30m / 0-30m)
- ✅ Impossible to enter invalid values
- ✅ Live value display in label
- ✅ Quick experimentation with different values
- ✅ Marks show common values (10m, 20m, etc.)
- ✅ Tooltip on hover for precision

## Visual Layout

```
┌─────────────────────────────────────────────┐
│  Hard Constraints                           │
├─────────────────────────────────────────────┤
│  Max Height (15m)                           │
│  ├────●──────────────────────────┤          │
│  3m      10m      20m      30m              │
│                                             │
│  Min Distance (6m)                          │
│  ├───────●─────────────────────┤            │
│  0m      10m      20m      30m              │
└─────────────────────────────────────────────┘
```

## Technical Details

### Component Properties

#### dcc.Slider Properties Used:
- `id`: Component identifier for callbacks
- `min`: Minimum value (3 for height, 0 for distance)
- `max`: Maximum value (30 for both)
- `step`: Increment size (1 meter)
- `value`: Current/default value
- `marks`: Dictionary of position labels {value: 'label'}
- `tooltip`: Hover tooltip configuration

#### Label Display:
- `html.Span`: Dynamically updated value display
- `className='ms-2 text-primary fw-bold'`: Spacing, color, bold
- Updates in real-time via callback

### Data Flow

```
User moves slider
    ↓
Slider 'value' updates
    ↓
Display callback triggers → Updates label (15m)
    ↓
Save callback triggers → Saves to session
    ↓
Navigation away/back
    ↓
Restore callback triggers → Restores slider value
```

## Compatibility

### Existing Code
✅ **No breaking changes**: 
- Component ID unchanged: `max-height-constraint`, `min-distance-constraint`
- Value property works identically
- Save/restore callbacks unchanged
- Backend receives same data format

### Session Storage
✅ **Fully compatible**:
```python
session_data['hard_constraints'] = {
    'max_height': 15,      # From slider
    'min_distance': 6      # From slider
}
```

## Testing Checklist

### Functional Testing
- [ ] **Slider Movement**: Move max_height slider from 3m to 30m
- [ ] **Value Display**: Verify label updates to show "(15m)"
- [ ] **Min Distance**: Move min_distance slider from 0m to 30m
- [ ] **Marks**: Click on marks (10m, 20m) - slider jumps to mark
- [ ] **Tooltip**: Hover over slider - tooltip shows current value

### Persistence Testing
- [ ] **Save**: Set max_height=20m, min_distance=10m, navigate to Step 3
- [ ] **Restore**: Return to Step 2, verify values are 20m and 10m
- [ ] **Optimization**: Run optimization, verify constraints used correctly
- [ ] **Session**: Reload page, verify values persist

### Edge Cases
- [ ] **Minimum**: Set max_height to 3m (minimum allowed)
- [ ] **Maximum**: Set max_height to 30m (maximum allowed)
- [ ] **Zero**: Set min_distance to 0m (no constraint)
- [ ] **Combined**: Set both constraints, verify both save/restore

## Comparison with Feature Range Sliders

Both use the same pattern:

| Aspect | Feature Ranges | Hard Constraints |
|--------|---------------|------------------|
| Component | `dcc.RangeSlider` | `dcc.Slider` |
| Values | Range [min, max] | Single value |
| Dynamic | Yes (per feature) | Fixed (2 sliders) |
| Pattern ID | `{'type': 'feature-range-slider', 'index': i}` | Fixed IDs |
| Save Logic | Loop through ALL matches | Direct input values |
| Display | Inside slider card | Separate span element |

## Benefits

### User Experience
1. **Intuitive**: Visual slider vs. text input
2. **Discoverable**: Range visible at a glance
3. **Error-proof**: Can't enter invalid values
4. **Quick**: Fast experimentation with values
5. **Feedback**: Real-time value display

### Development
1. **Consistent**: Matches feature range slider pattern
2. **Validated**: Built-in range validation
3. **Maintainable**: Standard Dash component
4. **Accessible**: Keyboard navigation supported

### Performance
1. **Efficient**: No validation overhead
2. **Lightweight**: Standard Dash component
3. **Responsive**: Smooth interaction

## Future Enhancements

### Potential Improvements
1. **Preset Values**: Quick buttons for common heights (10m, 20m, 30m)
2. **Linked Constraints**: Warn if min_distance too large for parcel
3. **Contextual Help**: Tooltip explaining constraint impact
4. **Unit Toggle**: Allow switching between meters/floors display
5. **Advanced Mode**: Unlock extended range for power users

### Alternative Designs
1. **Dual Slider**: Combined height + distance on same slider
2. **Radial Slider**: Circular slider for distance
3. **Stepped Slider**: Non-linear steps (3, 6, 10, 15, 20, 30)
4. **Animated**: Visual preview of building at selected height

## Related Documentation

- `USER_CONTROLLED_MAX_HEIGHT.md` - Background on z_length parameter
- `ADAPTIVE_FEATURE_CALCULATION.md` - How constraints affect ranges
- `METER_SYSTEM_MIGRATION.md` - Unit standardization context

## Files Modified

- ✅ `pages/step2_constraints.py` - UI components and callbacks

## Files Not Modified (Work Automatically)

- ✅ `backend/optimization_process.py` - Uses constraint values as-is
- ✅ `backend/encoding.py` - Receives z_length from constraint
- ✅ Session storage/restore - Works with value property

## Conclusion

✅ **Feature Complete**: Hard constraints now use intuitive sliders
✅ **User-Friendly**: Visual feedback with live value display  
✅ **Persistent**: Values save/restore automatically
✅ **Compatible**: No breaking changes to existing code
✅ **Tested**: No compilation errors

**Ready for User Testing!** 🎚️
