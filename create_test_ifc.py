#!/usr/bin/env python
"""Create a minimal test IFC file for the pipeline."""

import ifcopenshell

# Create a new IFC file
ifc_file = ifcopenshell.file(schema="IFC4")

# Create basic project structure
project = ifc_file.create_entity("IfcProject", Name="TestProject", GlobalId="0")

# Add a building
building = ifc_file.create_entity("IfcBuilding", Name="TestBuilding", GlobalId="1")
rel_agg = ifc_file.create_entity("IfcRelAggregates", GlobalId="2", RelatingObject=project, RelatedObjects=[building])

# Add a storey
storey = ifc_file.create_entity("IfcBuildingStorey", Name="Ground Floor", GlobalId="3")
rel_agg2 = ifc_file.create_entity("IfcRelAggregates", GlobalId="4", RelatingObject=building, RelatedObjects=[storey])

# Add a space (room)
space = ifc_file.create_entity("IfcSpace", Name="TestRoom", GlobalId="5")
rel_contains = ifc_file.create_entity("IfcRelContainedInSpatialStructure", GlobalId="6", 
                                     RelatingStructure=storey, RelatedElements=[space])

# Add a wall
wall = ifc_file.create_entity("IfcWall", Name="TestWall", GlobalId="7")
rel_contains2 = ifc_file.create_entity("IfcRelContainedInSpatialStructure", GlobalId="8", 
                                      RelatingStructure=storey, RelatedElements=[wall])

# Add a door hosted by wall
door = ifc_file.create_entity("IfcDoor", Name="TestDoor", GlobalId="9")
rel_connect = ifc_file.create_entity("IfcRelConnectsElements", GlobalId="10", 
                                    RelatingElement=wall, RelatedElement=door)

# Save the file
ifc_file.write("test.ifc")
print("Created test.ifc")
