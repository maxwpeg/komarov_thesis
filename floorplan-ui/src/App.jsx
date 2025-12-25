import React, { useState, useEffect } from "react";
import { Stage, Layer, Rect, Text } from "react-konva";

function App() {
  const [image, setImage] = useState(null);
  const [objects, setObjects] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    setImage(URL.createObjectURL(file));

    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/predict", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    setObjects(data.objects);
  };

  const handleDragEnd = (e, id) => {
    const newObjects = objects.map((obj) =>
      obj.id === id ? { ...obj, x: e.target.x(), y: e.target.y() } : obj
    );
    setObjects(newObjects);
  };

  const sendFeedback = async () => {
    await fetch("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objects }),
    });
    alert("Feedback saved!");
  };

  return (
    <div className="p-4">
      <h2>📐 Floor Plan Annotator</h2>
      <input type="file" accept="image/*" onChange={handleUpload} />
      <div>
        {image && (
          <Stage width={800} height={600}>
            <Layer>
              <image href={image} />
              {objects.map((obj) => (
                <Rect
                  key={obj.id}
                  x={obj.x}
                  y={obj.y}
                  width={obj.width}
                  height={obj.height}
                  fill="transparent"
                  stroke={obj.type === "wall" ? "brown" : obj.type === "door" ? "green" : "blue"}
                  draggable
                  onDragEnd={(e) => handleDragEnd(e, obj.id)}
                  onClick={() => setSelectedId(obj.id)}
                />
              ))}
            </Layer>
          </Stage>
        )}
      </div>
      <button onClick={sendFeedback}>💾 Save Feedback</button>
    </div>
  );
}

export default App;



