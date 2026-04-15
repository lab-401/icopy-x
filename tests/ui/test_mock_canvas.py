"""Smoke tests for MockCanvas — validates the test infrastructure itself."""

import pytest


class TestMockCanvasCreation:
    """Verify create_* methods return unique IDs and store items."""

    def test_create_rectangle(self, canvas):
        rid = canvas.create_rectangle(0, 0, 100, 50, fill="red")
        assert isinstance(rid, int)
        assert canvas.type(rid) == "rectangle"
        assert canvas.itemcget(rid, "fill") == "red"

    def test_create_text(self, canvas):
        tid = canvas.create_text(120, 120, text="Hello", fill="white")
        assert canvas.type(tid) == "text"
        assert canvas.itemcget(tid, "text") == "Hello"

    def test_create_image(self, canvas):
        iid = canvas.create_image(10, 20, image="placeholder")
        assert canvas.type(iid) == "image"

    def test_create_line(self, canvas):
        lid = canvas.create_line(0, 0, 100, 100, fill="blue")
        assert canvas.type(lid) == "line"
        assert canvas.coords(lid) == [0, 0, 100, 100]

    def test_create_oval(self, canvas):
        oid = canvas.create_oval(10, 10, 50, 50, outline="green")
        assert canvas.type(oid) == "oval"

    def test_create_polygon(self, canvas):
        pid = canvas.create_polygon(0, 0, 50, 100, 100, 0, fill="yellow")
        assert canvas.type(pid) == "polygon"
        assert canvas.coords(pid) == [0, 0, 50, 100, 100, 0]

    def test_ids_are_unique(self, canvas):
        a = canvas.create_rectangle(0, 0, 10, 10)
        b = canvas.create_text(5, 5, text="x")
        c = canvas.create_line(0, 0, 1, 1)
        assert len({a, b, c}) == 3


class TestMockCanvasTags:
    """Verify tag storage, lookup, and manipulation."""

    def test_tags_stored(self, canvas):
        rid = canvas.create_rectangle(0, 0, 10, 10, tags="tags_title")
        assert "tags_title" in canvas.gettags(rid)

    def test_tags_as_tuple(self, canvas):
        rid = canvas.create_rectangle(0, 0, 10, 10, tags=("a", "b"))
        tags = canvas.gettags(rid)
        assert "a" in tags
        assert "b" in tags

    def test_find_withtag(self, canvas):
        r1 = canvas.create_rectangle(0, 0, 10, 10, tags="layer1")
        r2 = canvas.create_rectangle(0, 0, 20, 20, tags="layer2")
        r3 = canvas.create_rectangle(0, 0, 30, 30, tags="layer1")
        found = canvas.find_withtag("layer1")
        assert r1 in found
        assert r3 in found
        assert r2 not in found

    def test_find_withtag_all(self, canvas):
        canvas.create_rectangle(0, 0, 10, 10)
        canvas.create_text(5, 5, text="x")
        assert len(canvas.find_withtag("all")) == 2

    def test_addtag_withtag(self, canvas):
        rid = canvas.create_rectangle(0, 0, 10, 10, tags="old")
        canvas.addtag_withtag("new", "old")
        assert "new" in canvas.gettags(rid)
        assert "old" in canvas.gettags(rid)

    def test_dtag(self, canvas):
        rid = canvas.create_rectangle(0, 0, 10, 10, tags=("a", "b"))
        canvas.dtag(rid, "a")
        assert "a" not in canvas.gettags(rid)
        assert "b" in canvas.gettags(rid)


class TestMockCanvasModification:
    """Verify itemconfig, coords, move."""

    def test_itemconfig_updates_options(self, canvas):
        tid = canvas.create_text(0, 0, text="old", fill="white")
        canvas.itemconfig(tid, text="new", fill="red")
        assert canvas.itemcget(tid, "text") == "new"
        assert canvas.itemcget(tid, "fill") == "red"

    def test_itemconfigure_alias(self, canvas):
        tid = canvas.create_text(0, 0, text="x")
        canvas.itemconfigure(tid, text="y")
        assert canvas.itemcget(tid, "text") == "y"

    def test_itemconfig_by_tag(self, canvas):
        r1 = canvas.create_rectangle(0, 0, 10, 10, tags="group", fill="red")
        r2 = canvas.create_rectangle(0, 0, 20, 20, tags="group", fill="red")
        canvas.itemconfig("group", fill="blue")
        assert canvas.itemcget(r1, "fill") == "blue"
        assert canvas.itemcget(r2, "fill") == "blue"

    def test_coords_get(self, canvas):
        rid = canvas.create_rectangle(5, 10, 15, 20)
        assert canvas.coords(rid) == [5, 10, 15, 20]

    def test_coords_set(self, canvas):
        rid = canvas.create_rectangle(0, 0, 10, 10)
        canvas.coords(rid, 1, 2, 3, 4)
        assert canvas.coords(rid) == [1, 2, 3, 4]

    def test_move(self, canvas):
        rid = canvas.create_rectangle(10, 20, 30, 40)
        canvas.move(rid, 5, -5)
        assert canvas.coords(rid) == [15, 15, 35, 35]

    def test_move_by_tag(self, canvas):
        r1 = canvas.create_rectangle(0, 0, 10, 10, tags="grp")
        r2 = canvas.create_rectangle(100, 100, 110, 110, tags="grp")
        canvas.move("grp", 1, 2)
        assert canvas.coords(r1) == [1, 2, 11, 12]
        assert canvas.coords(r2) == [101, 102, 111, 112]


class TestMockCanvasDeletion:
    """Verify delete by id, tag, and 'all'."""

    def test_delete_by_id(self, canvas):
        rid = canvas.create_rectangle(0, 0, 10, 10)
        canvas.delete(rid)
        assert canvas.find_all() == ()

    def test_delete_by_tag(self, canvas):
        r1 = canvas.create_rectangle(0, 0, 10, 10, tags="temp")
        r2 = canvas.create_rectangle(0, 0, 10, 10, tags="keep")
        canvas.delete("temp")
        assert r1 not in canvas.find_all()
        assert r2 in canvas.find_all()

    def test_delete_all(self, canvas):
        canvas.create_rectangle(0, 0, 10, 10)
        canvas.create_text(5, 5, text="x")
        canvas.delete("all")
        assert canvas.find_all() == ()


class TestMockCanvasQuery:
    """Verify bbox, winfo, find methods."""

    def test_bbox(self, canvas):
        canvas.create_rectangle(10, 20, 30, 40)
        bb = canvas.bbox("all")
        assert bb == (10, 20, 30, 40)

    def test_bbox_multiple(self, canvas):
        canvas.create_rectangle(10, 20, 30, 40)
        canvas.create_rectangle(5, 50, 100, 60)
        bb = canvas.bbox("all")
        assert bb == (5, 20, 100, 60)

    def test_bbox_none_for_missing(self, canvas):
        assert canvas.bbox("nonexistent") is None

    def test_winfo_dimensions(self, canvas):
        assert canvas.winfo_width() == 240
        assert canvas.winfo_height() == 240

    def test_type_missing(self, canvas):
        assert canvas.type(999) == ""

    def test_gettags_missing(self, canvas):
        assert canvas.gettags(999) == ()


class TestMockCanvasAfter:
    """Verify after/after_cancel and fire helpers."""

    def test_after_stores_callback(self, canvas):
        called = []
        timer = canvas.after(1000, lambda: called.append(True))
        assert timer.startswith("after#")
        assert len(called) == 0  # Not auto-executed

    def test_fire_after(self, canvas):
        called = []
        timer = canvas.after(500, lambda: called.append("fired"))
        canvas.fire_after(timer)
        assert called == ["fired"]
        # Timer removed after firing
        assert timer not in canvas._timers

    def test_after_cancel(self, canvas):
        timer = canvas.after(100, lambda: None)
        canvas.after_cancel(timer)
        assert timer not in canvas._timers

    def test_fire_all_after(self, canvas):
        results = []
        canvas.after(100, lambda: results.append("a"))
        canvas.after(200, lambda: results.append("b"))
        canvas.fire_all_after()
        assert set(results) == {"a", "b"}
        assert len(canvas._timers) == 0

    def test_after_with_args(self, canvas):
        results = []
        timer = canvas.after(100, results.append, "hello")
        canvas.fire_after(timer)
        assert results == ["hello"]


class TestMockCanvasHelpers:
    """Verify test-only helper methods."""

    def test_get_items_by_type(self, canvas):
        canvas.create_rectangle(0, 0, 10, 10)
        canvas.create_text(5, 5, text="hi")
        canvas.create_rectangle(0, 0, 20, 20)
        rects = canvas.get_items_by_type("rectangle")
        assert len(rects) == 2
        texts = canvas.get_items_by_type("text")
        assert len(texts) == 1

    def test_get_item(self, canvas):
        rid = canvas.create_rectangle(0, 0, 10, 10, fill="red", tags="bg")
        item = canvas.get_item(rid)
        assert item["type"] == "rectangle"
        assert item["options"]["fill"] == "red"
        assert "bg" in item["tags"]

    def test_get_item_missing(self, canvas):
        assert canvas.get_item(999) is None

    def test_get_all_text(self, canvas):
        canvas.create_text(0, 0, text="Line 1")
        canvas.create_text(0, 20, text="Line 2")
        canvas.create_rectangle(0, 0, 10, 10)
        texts = canvas.get_all_text()
        assert "Line 1" in texts
        assert "Line 2" in texts
        assert len(texts) == 2

    def test_snapshot_is_deep_copy(self, canvas):
        canvas.create_rectangle(0, 0, 10, 10, fill="red")
        snap = canvas.snapshot()
        canvas.delete("all")
        # Snapshot is unaffected by subsequent mutations
        assert len(snap["items"]) == 1
        assert snap["width"] == 240


class TestMockCanvasLayoutNoOps:
    """Verify layout methods don't crash."""

    def test_grid(self, canvas):
        canvas.grid(row=0, column=0)

    def test_grid_remove(self, canvas):
        canvas.grid_remove()

    def test_pack(self, canvas):
        canvas.pack(fill="both")

    def test_place(self, canvas):
        canvas.place(x=0, y=0)

    def test_destroy(self, canvas):
        canvas.create_rectangle(0, 0, 10, 10)
        canvas.destroy()
        assert canvas.find_all() == ()

    def test_update(self, canvas):
        canvas.update()

    def test_update_idletasks(self, canvas):
        canvas.update_idletasks()
