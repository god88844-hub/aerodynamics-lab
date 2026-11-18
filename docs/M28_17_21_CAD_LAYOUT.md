# M28.17–M28.21 CAD exchange for component positions

## M28.17 Export a saved revision

In the design editor, select a saved design and revision, then download its DXF layout. The file name includes the design ID, revision number, and a prefix of the source snapshot's SHA-256. Each point carries the full snapshot digest and item key as DXF extended data. Two revisions with exactly the same canonical snapshot can use the same drawing. The drawing uses R2010 text DXF and explicitly declares metres. [ezdxf document formats](https://ezdxf.mozman.at/docs/drawing/management.html)

## M28.18 Edit model-space points

Each independent part center of gravity, rotor thrust center and frame mount appears as a 3D point in the design body frame. The layer identifies the item type, index and name. A mounted part follows its mount automatically. Rotor positions and unmounted part centers are independent design inputs. When moving a rotor assembly, move its associated motor, propeller and any other components to the intended positions. CAD coordinates describe placement only. Solid bodies, shape edits and fabrication tolerances require separate drawings.

## M28.19 Preview and check the drawing

Choose the edited DXF in the same saved revision. The API requires metre units, preserved point identity and layer names, finite coordinates, and one copy of every expected model-space point. A mismatched snapshot, changed entity type, added geometry or missing point rejects the import. The upload limit is 1 MiB. The editor lists each changed position, including mounted parts. Numerical masses, inertias, component IDs, rotor spin, primitive dimensions, material properties and notes come from the saved source revision.

## M28.20 Save the edited copy

Review the coordinates and choose **Save CAD changes as new design**. The saved copy appears in the design list with its own ID and revision history. The export and preview operate on the selected saved revision. They leave the source history and the active editor draft intact.

## M28.21 Verify the round trip

The integration test checks an unchanged round trip, a moved rotor and battery mount, preservation of all other fields, source immutability, and rejection of invalid drawings. The packaged-browser test downloads the DXF, edits the battery point through ezdxf, previews the change, saves a copy, and compares the complete resulting snapshot.

```console
python -m pytest tests/integration/test_api.py -k cad_layout
```

The drawing supports placement exchange for AeroForge designs. General CAD solid import, validated assembly tolerances and broader M28 acceptance remain open.
