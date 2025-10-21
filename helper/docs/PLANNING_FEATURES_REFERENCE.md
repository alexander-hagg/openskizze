# Quick Reference: Planning-Focused Features

## Feature Descriptions

### 0. GRZ (Grundflächenzahl / Site Coverage Ratio)
**Definition:** The ratio of built ground area to total site area.  
**Formula:** `GRZ = Built Area (m²) / Site Area (m²)`  
**Range:** 0.0 - 1.0 (cannot exceed 1.0)  
**Unit:** Dimensionless ratio  
**Planning Context:** 
- German planning regulation parameter
- Defines maximum allowable building footprint
- Typical values:
  - Low-density residential: 0.2-0.4
  - Medium-density: 0.4-0.6
  - High-density urban: 0.6-0.8

### 1. GFZ (Geschossflächenzahl / Floor Area Ratio)
**Definition:** The ratio of total floor area to site area.  
**Formula:** `GFZ = Total Floor Area (m²) / Site Area (m²)`  
**Range:** 0.0+ (can exceed 1.0 for multi-story)  
**Unit:** Dimensionless ratio  
**Planning Context:**
- Controls building density and height
- Can be >1.0 for multi-story buildings
- Typical values:
  - Low-density residential: 0.4-0.8
  - Medium-density: 0.8-2.0
  - High-density urban: 2.0-5.0+
- Relationship: `GFZ = GRZ × Average_Number_of_Floors`

### 2. Average Building Height (m)
**Definition:** Mean height of all buildings in the design.  
**Formula:** `Mean(height of all occupied cells)`  
**Range:** 0 - Max Height Constraint  
**Unit:** Meters (m)  
**Same as Original Feature Set #1**

### 3. Height Variability (m)
**Definition:** Standard deviation of building heights.  
**Formula:** `StdDev(height of all occupied cells)`  
**Range:** 0+ meters  
**Unit:** Meters (m)  
**Planning Context:** 
- Low variability: uniform skyline
- High variability: mixed-height development
**Same as Original Feature Set #2**

### 4. Number of Buildings
**Definition:** Count of distinct building structures.  
**Formula:** Connected component labeling  
**Range:** 0 - Max Buildings (10 in current config)  
**Unit:** Count (dimensionless)  
**Same as Original Feature Set #3**

### 5. Average Building Distance (m)
**Definition:** Mean Euclidean distance between building centroids.  
**Formula:** `Mean(pairwise distances between centroids)`  
**Range:** Min Distance Constraint - Grid Diagonal  
**Unit:** Meters (m)  
**Same as Original Feature Set #4**

### 6. Street Canyon Aspect Ratio (H/W)
**Definition:** Ratio of building height to street width.  
**Formula:** `H/W = Average Height / Average Distance`  
**Range:** 0+ (typically 0.5-3.0 in urban contexts)  
**Unit:** Dimensionless ratio  
**Planning Context:**
- H/W < 0.5: Open, well-ventilated spaces
- H/W 0.5-1.0: Comfortable pedestrian scale
- H/W 1.0-2.0: Urban street canyon
- H/W > 2.0: Deep canyon, reduced ventilation
- Important for wind flow, daylight, and microclimate

### 7. Sky View Factor (SVF)
**Definition:** Proportion of sky visible from ground level.  
**Formula (Current):** `SVF ≈ 1 - (GRZ × Normalized_Height × 0.8)`  
**Range:** 0.0 - 1.0  
**Unit:** Dimensionless ratio (0-1)  
**Planning Context:**
- SVF = 1.0: Complete open sky
- SVF = 0.5: Half sky obscured
- SVF = 0.0: Completely enclosed
- Affects: heat island effect, daylight, solar access
**Note:** Current implementation is a simplified approximation. Full ray-tracing SVF calculation is marked for future enhancement.

---

## Feature Comparison Table

| Feature | Original Set | Planning Set | Unit | Typical Range |
|---------|-------------|--------------|------|---------------|
| 0 | Built Area | **GRZ** | m² / ratio | - / 0.2-0.8 |
| 1 | Avg Height | Avg Height | m | 3-30m |
| 2 | Height Var. | Height Var. | m | 0-15m |
| 3 | Num Buildings | Num Buildings | count | 1-10 |
| 4 | Avg Distance | Avg Distance | m | 6-100m |
| 5 | **Gross Floor Area** | **GFZ** | m² / ratio | - / 0.5-5.0 |
| 6 | Building Mass X | **H/W Ratio** | 0-1 / ratio | - / 0.5-3.0 |
| 7 | Building Mass Y | **SVF** | 0-1 / 0-1 | 0-1 / 0-1 |

---

## Usage Examples

### Example 1: Low-Density Residential
```
GRZ: 0.25 (25% coverage)
GFZ: 0.50 (equivalent to 2 floors average)
Avg Height: 6m
H/W Ratio: 0.12 (very open)
SVF: 0.95 (excellent sky visibility)
```

### Example 2: Dense Urban
```
GRZ: 0.60 (60% coverage)
GFZ: 3.60 (equivalent to 6 floors average)
Avg Height: 18m
H/W Ratio: 0.90 (moderate canyon)
SVF: 0.60 (partial sky obstruction)
```

### Example 3: Street Canyon
```
GRZ: 0.40 (40% coverage)
GFZ: 2.40 (equivalent to 6 floors average)
Avg Height: 18m
Avg Distance: 45m (street width)
H/W Ratio: 0.40 (comfortable scale)
SVF: 0.85 (good sky visibility)
```

---

## Mathematical Relationships

### GRZ and GFZ
- If all buildings have same height h:  
  `GFZ = GRZ × (h / floor_height)`
  
- For variable heights:  
  `GFZ = Sum(height_i × area_i) / Site_Area`

### H/W and Microclimate
- Lower H/W → Better wind ventilation
- Higher H/W → More shade, less direct sunlight
- Optimal H/W for thermal comfort: typically 0.5-1.0

### SVF and Urban Heat Island
- Higher SVF → Better cooling at night
- Lower SVF → Heat retention, reduced cooling
- SVF < 0.4 often associated with UHI effects

---

## Validation Criteria

When reviewing optimization results, check for:

1. **GRZ Feasibility:** Should be ≤ 1.0
2. **GFZ Consistency:** Should roughly equal GRZ × avg_floors
3. **H/W Realism:** Typically 0.3-3.0 for urban contexts
4. **SVF Physical Limits:** Must be 0.0-1.0
5. **Planning Regulations:** Compare against local zoning requirements

---

## References

- GRZ/GFZ: German BauNVO (Baunutzungsverordnung)
- H/W Ratio: Oke (1988), "Street design and urban canopy layer climate"
- SVF: Grimmond & Oke (1999), "Heat storage in urban areas"
