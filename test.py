import time
from core.llm.llm_filter_image import FilterImage
from queue_llm import ImageProcessingQueue, TaskStatus


# ---------- callback ----------
def on_task_update(task_id, status, result=None, error=None):
    short_id = task_id[:8]

    if status == TaskStatus.PROCESSING:
        print(f"[CALLBACK] {short_id} started processing")

    elif status == TaskStatus.DONE:
        print(f"[CALLBACK] {short_id} DONE → result={result}")

    elif status == TaskStatus.ERROR:
        print(f"[CALLBACK] {short_id} ERROR → {error}")


# ---------- test ----------
def test_image_queue_callback():
    queue = ImageProcessingQueue(
        FilterImage(),
        on_task_done=on_task_update
    )

    image_paths = [
        "/Users/mor/Downloads/Gemini_Generated_Image_t1uzpyt1uzpyt1uz.png",
        "/Users/mor/Downloads/Gemini_Generated_Image_svcyrusvcyrusvcy.png",
        "/Users/mor/Downloads/Gemini_Generated_Image_ip0y68ip0y68ip0y.png",
        "/Users/mor/Downloads/Gemini_Generated_Image_a3lm4la3lm4la3lm.png",
        "/Users/mor/Downloads/Gemini_Generated_Image_4asiyu4asiyu4asi.png",
    ]

    for path in image_paths:
        task_id = queue.enqueue(path)
        print(f"[MAIN] sent {path} → task_id={task_id[:8]}")

    print("[MAIN] Waiting for queue to finish...\n")

    queue.wait_until_done()   # ⬅️ כאן הקסם

    print("\n[MAIN] All tasks completed. Exiting.")



if __name__ == "__main__":
    test_image_queue_callback()
