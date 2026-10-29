# Terrain, placement and gravity

## Terrain and placement

Point height, voxel signed-distance generation, meshes and creature queries are separate stages. A
point-height helper omits layers and caves used by the voxel path. Spawn depth is not discovery
height.

Placement combines lattice origins, cells, seeds, role activity, body clearance and terrain.
Population candidates do not establish completed paths. Query samples, source planet and owner must
belong to the same generation. Average query depth can affect subsequent underwater scale.

Generated buildings, cached regions, unique-region overrides and saved sites can affect terrain
inputs. Omitting them can explain differences from native terrain. Requests also require complete
radius and source-bound inputs. Body bounds depend on selected descriptors, attachments, transforms
and cache choices; a family name alone is not a clearance radius.

## Transforms

Facing uses position, direction and gravity. Native code normalizes/reconstructs basis rows and
applies spawn scale. The scene world setter converts through parent space; the getter composes the
hierarchy before size measurement. Translation and basis occupy distinct lanes. Inverse/forward
floating-point operations do not cancel exactly and can affect a cutoff comparison.

The initialized chain contains scene-manager root, Simulation-Root and Creatures. Scene handles
carry slot/generation identity; reused slots are not the same node lifetime.

## Gravity

The manager accepts planetary spheres and local volumes. Local routes include game/Toolkit gravity
components, particular Outpost routes, space/ship routes and admitted base parts. A metadata flag
does not establish an active field: owner type, selected scene, activation and registration matter.

`GcBaseBuildingEntry` contains `HasGravity`, `GravityStrength` and `GravityFalloff`, separately from
ordinary `TkPhysicsData`. The retained ordinary persistent planetary-base load route normalizes its
owner to a value rejected by the local-gravity admission gate. Other routes have separate rules.

Toolkit components use override bounds, falloff radius, strength and `MoveWithParent`. Movement
changes the registered centre/radius but retains the registration-time direction. Re-registration
can capture a new direction; the current scene's second row is not necessarily that direction.
Generation-qualified retirement prevents an old handle from altering a replacement field.

The gravitational-anomaly hazard has a moving Toolkit gravity component and authored `NotInStorm`
condition. A gravitational-storm label alone neither proves nor excludes activation. Planetary
Outpost and spacecraft/Nexus attachments are different sources despite similar path terms.

## Buildings and collision

Settlement building-owner/region records differ from ordinary player bases. Leaving and returning
can retire and reconstruct records. Parent transforms, local positions and physics-world conversion
are separate inputs. Modular bounds depend on completed parts, snap counts and variants.

Sphere, box, convex and mesh collision queries have different shape contexts. World hit position
depends on context, scale, transforms and hit fraction. A fraction alone is not a world position; a
broadphase candidate is not a confirmed hit.
