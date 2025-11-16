import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="SaaS Todo API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API
class TodoIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    completed: bool = False
    priority: Optional[str] = Field(None)

class TodoOut(TodoIn):
    id: str


def serialize_todo(doc) -> TodoOut:
    return TodoOut(
        id=str(doc.get("_id")),
        title=doc.get("title", ""),
        description=doc.get("description"),
        completed=doc.get("completed", False),
        priority=doc.get("priority"),
    )


@app.get("/")
def read_root():
    return {"message": "SaaS Todo API running"}


@app.get("/api/todos", response_model=List[TodoOut])
def list_todos():
    try:
        docs = get_documents("todo", {}, limit=100)
        return [serialize_todo(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/todos", response_model=TodoOut)
def create_todo(payload: TodoIn):
    try:
        inserted_id = create_document("todo", payload)
        # Fetch the created document
        doc = db["todo"].find_one({"_id": ObjectId(inserted_id)})
        return serialize_todo(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/todos/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: str, payload: TodoIn):
    try:
        oid = ObjectId(todo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    try:
        update = {k: v for k, v in payload.model_dump().items() if v is not None}
        update["updated_at"] = __import__("datetime").datetime.utcnow()
        res = db["todo"].find_one_and_update(
            {"_id": oid},
            {"$set": update},
            return_document=True,
        )
        if not res:
            raise HTTPException(status_code=404, detail="Not found")
        return serialize_todo(res)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/todos/{todo_id}")
def delete_todo(todo_id: str):
    try:
        oid = ObjectId(todo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    try:
        res = db["todo"].delete_one({"_id": oid})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
