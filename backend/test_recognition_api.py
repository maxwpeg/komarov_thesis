"""
Test the floor plan recognition API endpoints.
"""

import pytest
import json
import os
from pathlib import Path
from PIL import Image
import numpy as np

# Mock test - would need actual FastAPI app instance
# This is a reference implementation for what the tests should look like

def test_recognition_api_structure():
    """Verify that the API can import and structure the recognition module."""
    from backend.models import FloorplanRecognition, FloorPlan
    from backend.floorplan_integration import get_integrator
    
    # Test that integrator can be created
    integrator = get_integrator()
    assert integrator is not None
    print(f"✓ Integrator created: {type(integrator)}")
    
    # Test that FloorplanRecognition model has required methods
    assert hasattr(FloorplanRecognition, 'to_dict')
    print(f"✓ FloorplanRecognition has to_dict method")
    
    # Test that FloorPlan has relationship to FloorplanRecognition
    from sqlalchemy import inspect
    fp_mapper = inspect(FloorPlan)
    relationships = {rel.key: rel for rel in fp_mapper.relationships}
    assert 'floorplan_recognition' in relationships
    print(f"✓ FloorPlan has floorplan_recognition relationship")


def test_integrator_methods():
    """Test that integrator has all required methods."""
    from backend.floorplan_integration import FloorplanRecognitionIntegrator
    
    integrator = FloorplanRecognitionIntegrator()
    
    # Check methods exist
    assert hasattr(integrator, 'recognize_floor_plan')
    assert hasattr(integrator, 'convert_to_database_models')
    assert hasattr(integrator, 'result_to_dict')
    
    print(f"✓ Integrator has all required methods")


def test_result_dict_format():
    """Test that result_to_dict produces correct format and is JSON serializable."""
    from backend.floorplan_integration import get_integrator
    from floorplan import ProcessingResult, Wall, Opening, OpeningType
    from floorplan.types import Point, LineSegment
    import numpy as np
    
    integrator = get_integrator()
    
    # Create a mock ProcessingResult with NumPy types (simulating real data)
    mock_wall = Wall(
        id=1,
        midline=LineSegment(
            x1=np.float64(0.0), 
            y1=np.float64(0.0), 
            x2=np.float64(100.0), 
            y2=np.float64(100.0)
        ),
        thickness_px=np.float32(10.0),
        angle_deg=np.float64(45.0),
        confidence=np.float64(0.95)
    )
    
    mock_opening = Opening(
        type=OpeningType.DOOR,
        wall_id=1,
        bbox=(np.intc(50), np.intc(50), np.intc(80), np.intc(80)),  # NumPy int types
        confidence=np.float64(0.85),
        center=(np.float32(65.0), np.float32(65.0)),  # NumPy float types
        marker=None,
        lines=[],
        metadata={}
    )
    
    result = ProcessingResult(
        image_width=np.int32(400),  # NumPy int
        image_height=np.int32(400),
        walls=[mock_wall],
        openings=[mock_opening]
    )
    
    # Convert to dict
    result_dict = integrator.result_to_dict(result)
    
    # Verify structure
    assert 'image' in result_dict
    assert 'walls' in result_dict
    assert 'openings' in result_dict
    assert result_dict['image']['width'] == 400
    assert result_dict['image']['height'] == 400
    assert len(result_dict['walls']) == 1
    assert len(result_dict['openings']) == 1
    assert result_dict['openings'][0]['type'] == 'door'
    
    # Test JSON serialization (this would fail without NumPy conversion)
    try:
        json_str = json.dumps(result_dict)
        print(f"✓ Result dict is JSON serializable")
    except TypeError as e:
        raise AssertionError(f"Result dict is not JSON serializable: {e}")
    
    print(f"✓ Result dict format is correct")
    print(f"  Walls: {len(result_dict['walls'])}")
    print(f"  Openings: {len(result_dict['openings'])}")


def test_database_model_conversion():
    """Test converting ProcessingResult to database models."""
    from backend.floorplan_integration import get_integrator
    from floorplan import ProcessingResult, Wall, Opening, OpeningType
    from floorplan.types import Point, LineSegment
    import numpy as np
    
    integrator = get_integrator()
    
    # Create mock result with NumPy types
    mock_wall = Wall(
        id=1,
        midline=LineSegment(
            x1=np.float64(10), 
            y1=np.float64(20), 
            x2=np.float64(110), 
            y2=np.float64(120)
        ),
        thickness_px=np.float32(8.0),
        angle_deg=np.float64(45.0),
        confidence=np.float64(0.95)
    )
    
    mock_door = Opening(
        type=OpeningType.DOOR,
        wall_id=1,
        bbox=(np.intc(50), np.intc(50), np.intc(80), np.intc(70)),
        confidence=np.float64(0.90),
        center=(np.float32(65), np.float32(60)),
        marker=None,
        lines=[],
        metadata={}
    )
    
    mock_window = Opening(
        type=OpeningType.WINDOW,
        wall_id=1,
        bbox=(np.intc(90), np.intc(90), np.intc(110), np.intc(100)),
        confidence=np.float64(0.85),
        center=(np.float32(100), np.float32(95)),
        marker=None,
        lines=[],
        metadata={}
    )
    
    result = ProcessingResult(
        image_width=np.int32(400),
        image_height=np.int32(400),
        walls=[mock_wall],
        openings=[mock_door, mock_window]
    )
    
    # Convert to models
    walls, doors, windows = integrator.convert_to_database_models(result, floor_plan_id=1)
    
    # Verify conversion
    assert len(walls) == 1
    assert len(doors) == 1
    assert len(windows) == 1
    
    assert walls[0].floor_plan_id == 1
    assert walls[0].x1 == 10.0  # Should be converted to float
    assert walls[0].y1 == 20.0
    assert walls[0].x2 == 110.0
    assert walls[0].y2 == 120.0
    
    assert doors[0].floor_plan_id == 1
    assert doors[0].x == 50.0
    assert doors[0].y == 50.0
    assert doors[0].width == 30.0
    assert doors[0].height == 20.0
    
    assert windows[0].window_type == "standard"
    
    print(f"✓ Database model conversion works correctly")
    print(f"  Walls: {len(walls)}")
    print(f"  Doors: {len(doors)}")
    print(f"  Windows: {len(windows)}")


if __name__ == '__main__':
    print("Testing Floor Plan Recognition API Integration...\n")
    
    try:
        test_recognition_api_structure()
        print()
        test_integrator_methods()
        print()
        test_result_dict_format()
        print()
        test_database_model_conversion()
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
