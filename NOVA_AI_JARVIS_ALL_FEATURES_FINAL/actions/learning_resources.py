from __future__ import annotations

import webbrowser
from typing import Optional

CURATED_RESOURCES = {
    "dsa": {
        "title": "Data Structures & Algorithms (DSA)",
        "roadmap": "https://roadmap.sh/datastructures-and-algorithms",
        "youtube_channels": [
            {"name": "take U forward (Striver)", "focus": "A2Z DSA Course, SDE Sheet, Tree/Graph/DP deep-dives", "url": "https://www.youtube.com/@takeUforward"},
            {"name": "NeetCode", "focus": "LeetCode problem walkthroughs, Blind 75, NeetCode 150", "url": "https://www.youtube.com/@NeetCode"},
            {"name": "Abdul Bari", "focus": "Intuitive theoretical algorithms and Big-O mastery", "url": "https://www.youtube.com/@abdul_bari"},
            {"name": "freeCodeCamp", "focus": "Full 5+ hour comprehensive DSA courses in C++/Python/Java", "url": "https://www.youtube.com/@freecodecamp"}
        ],
        "practice_sites": [
            {"name": "LeetCode", "url": "https://leetcode.com/"},
            {"name": "NeetCode 150 Roadmap", "url": "https://neetcode.io/practice"},
            {"name": "GeeksforGeeks DSA", "url": "https://www.geeksforgeeks.org/data-structures/"},
            {"name": "Striver's A2Z Sheet", "url": "https://takeuforward.org/strivers-a2z-dsa-course/strivers-a2z-dsa-course-sheet-2"}
        ],
        "tips": [
            "1. Master the fundamentals: Arrays, Strings, Hash Maps, and Two Pointers.",
            "2. Learn Recursion thoroughly before tackling Trees and Dynamic Programming.",
            "3. Practice patterns (Sliding Window, Binary Search, DFS/BFS) rather than memorizing individual solutions."
        ]
    },
    "python": {
        "title": "Python Programming",
        "roadmap": "https://roadmap.sh/python",
        "youtube_channels": [
            {"name": "Corey Schafer", "focus": "In-depth Python tutorials, OOP, standard library, and best practices", "url": "https://www.youtube.com/@coreyms"},
            {"name": "freeCodeCamp Python", "focus": "Beginner to advanced complete Python bootcamps", "url": "https://www.youtube.com/@freecodecamp"},
            {"name": "mCoding", "focus": "Modern Python tips, internals, and advanced patterns", "url": "https://www.youtube.com/@mCoding"},
            {"name": "Programming with Mosh", "focus": "Fast-paced beginner Python crash course", "url": "https://www.youtube.com/@programmingwithmosh"}
        ],
        "practice_sites": [
            {"name": "Official Python Docs", "url": "https://docs.python.org/3/tutorial/"},
            {"name": "Exercism Python Track", "url": "https://exercism.org/tracks/python"},
            {"name": "Real Python", "url": "https://realpython.com/"}
        ],
        "tips": [
            "1. Start with Python core syntax, data structures (lists, dicts, sets, tuples), and list comprehensions.",
            "2. Practice OOP concepts, context managers, generators, and decorators.",
            "3. Build real projects (CLI tools, automation scripts, web scrapers, APIs)."
        ]
    },
    "machine_learning": {
        "title": "Machine Learning & AI",
        "roadmap": "https://roadmap.sh/ai-data-scientist",
        "youtube_channels": [
            {"name": "StatQuest with Josh Starmer", "focus": "Intuitive visual explanations of ML algorithms & math", "url": "https://www.youtube.com/@statquest"},
            {"name": "3Blue1Brown", "focus": "Essence of Linear Algebra, Calculus, and Neural Networks", "url": "https://www.youtube.com/@3blue1brown"},
            {"name": "Andrew Ng (DeepLearning.AI)", "focus": "Machine Learning Specialization and foundational theory", "url": "https://www.youtube.com/@Deeplearningai"},
            {"name": "sentdex", "focus": "Practical Python ML, PyTorch, and reinforcement learning", "url": "https://www.youtube.com/@sentdex"}
        ],
        "practice_sites": [
            {"name": "Kaggle", "url": "https://www.kaggle.com/"},
            {"name": "Fast.ai", "url": "https://course.fast.ai/"},
            {"name": "Hugging Face Learn", "url": "https://huggingface.co/learn"}
        ],
        "tips": [
            "1. Understand Linear Algebra, Probability, and Gradient Descent intuitively.",
            "2. Implement classical algorithms (Linear/Logistic Regression, Random Forest, SVM) with scikit-learn.",
            "3. Move to PyTorch for Deep Learning and participate in Kaggle community competitions."
        ]
    },
    "web_development": {
        "title": "Web Development (Full Stack)",
        "roadmap": "https://roadmap.sh/full-stack",
        "youtube_channels": [
            {"name": "Kevin Powell", "focus": "CSS mastery and modern responsive design", "url": "https://www.youtube.com/@KevinPowell"},
            {"name": "Traversy Media", "focus": "Practical crash courses for web technologies and frameworks", "url": "https://www.youtube.com/@TraversyMedia"},
            {"name": "Fireship", "focus": "Fast 100-second overviews and modern dev trends", "url": "https://www.youtube.com/@Fireship"},
            {"name": "Web Dev Simplified", "focus": "Clean React, JavaScript, and backend tutorials", "url": "https://www.youtube.com/@WebDevSimplified"}
        ],
        "practice_sites": [
            {"name": "MDN Web Docs", "url": "https://developer.mozilla.org/"},
            {"name": "The Odin Project", "url": "https://www.theodinproject.com/"},
            {"name": "Frontend Mentor", "url": "https://www.frontendmentor.io/"}
        ],
        "tips": [
            "1. Build solid foundations in HTML5, modern CSS (Flexbox/Grid), and Vanilla JavaScript.",
            "2. Learn a frontend framework (React/Next.js or Vue) and state management.",
            "3. Build RESTful APIs, integrate databases (PostgreSQL/MongoDB), and deploy projects."
        ]
    }
}


def _match_topic_key(topic: str) -> str:
    low = (topic or "").lower().strip()
    if any(k in low for k in ("dsa", "data structure", "algorithm", "algo", "leet", "codeforces")):
        return "dsa"
    if any(k in low for k in ("python", "py")):
        return "python"
    if any(k in low for k in ("machine learning", "ml", "ai", "artificial intelligence", "deep learning", "data science")):
        return "machine_learning"
    if any(k in low for k in ("web dev", "frontend", "backend", "fullstack", "full stack", "javascript", "react", "html", "css")):
        return "web_development"
    return ""


def learning_resources(parameters: dict, player=None, **kwargs) -> str:
    topic = str(parameters.get("topic", "")).strip()
    open_in_browser = bool(parameters.get("open_in_browser", False))
    key = _match_topic_key(topic)

    if key and key in CURATED_RESOURCES:
        data = CURATED_RESOURCES[key]
        lines = [f"📚 Curated Learning Guide for {data['title']}:", ""]
        
        lines.append("🎥 Top Recommended YouTube Channels:")
        for ch in data["youtube_channels"]:
            lines.append(f"  • {ch['name']} — {ch['focus']}")
            lines.append(f"    Link: {ch['url']}")
        lines.append("")

        lines.append("🗺️ Recommended Roadmap & Practice:")
        lines.append(f"  • Roadmap: {data['roadmap']}")
        for site in data["practice_sites"]:
            lines.append(f"  • {site['name']}: {site['url']}")
        lines.append("")

        lines.append("💡 Strategy & Tips:")
        for tip in data["tips"]:
            lines.append(f"  {tip}")

        if open_in_browser:
            primary_url = data["youtube_channels"][0]["url"]
            try:
                webbrowser.open(primary_url)
                lines.append(f"\n🌐 Opened {data['youtube_channels'][0]['name']} in your browser.")
            except Exception:
                pass

        result = "\n".join(lines)
    else:
        # General topic
        clean_topic = topic or "Programming"
        yt_search = f"https://www.youtube.com/results?search_query={clean_topic.replace(' ', '+')}+tutorial+for+beginners"
        roadmap_url = f"https://roadmap.sh"
        
        lines = [
            f"📚 Learning Resources for '{clean_topic}':",
            "",
            f"🎥 YouTube Search for Top Tutorials: {yt_search}",
            f"🗺️ Developer Roadmaps: {roadmap_url}",
            "",
            "💡 Recommended Approach:",
            f"1. Search YouTube for high-rated beginner tutorials on '{clean_topic}'.",
            "2. Read the official documentation and reference guides.",
            "3. Build a small hands-on project to solidify your understanding."
        ]
        if open_in_browser:
            try:
                webbrowser.open(yt_search)
                lines.append(f"\n🌐 Opened YouTube tutorials for '{clean_topic}' in your browser.")
            except Exception:
                pass
        result = "\n".join(lines)

    if player and hasattr(player, "write_log"):
        player.write_log(f"[learning] Guide prepared for {topic}")
    return result


TOOL = {
    "name": "learning_resources",
    "description": "Provides roadmaps, recommended YouTube channels, websites, documentation, and practice resources for learning topics (e.g. DSA, Python, Machine Learning, Web Development). Can also optionally open curated resources in the browser.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "topic": {
                "type": "STRING",
                "description": "Subject or skill to learn, e.g. 'DSA', 'Python', 'Machine Learning'"
            },
            "open_in_browser": {
                "type": "BOOLEAN",
                "description": "Whether to open a top resource or search in browser"
            }
        },
        "required": ["topic"]
    },
    "handler": learning_resources
}
