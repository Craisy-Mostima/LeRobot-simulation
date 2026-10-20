#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LIBERO Custom Task Builder
--------------------------
固定使用 Scene A / B / C。

1. 选择场景；
2. 输入英文自然语言任务；
3. 脚本会将任务解析为 LIBERO Goal；
4. 自动生成新的 BDDL；
5. 加载环境并验证；
6. 保存一张自定义任务的初始场景预览图。

注意：
- 这是“受控自然语言”，不是任意开放式自然语言。
- 任务必须使用场景中已经存在的 objects / fixtures / regions。
- 该脚本只负责“创建 + 验证任务”，不会调用 SmolVLA 执行动作。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv
import libero.libero.envs.bddl_utils as BDDLUtils


# ============================================================
# Global configuration
# ============================================================

PROJECT_ROOT = Path.home() / "lerobot"
OUTPUT_ROOT = PROJECT_ROOT / "custom_libero_tasks"

CAMERA_HEIGHT = 512
CAMERA_WIDTH = 512
SHOW_IMAGE = True


SCENES = {
    "A": {
        "name": "Kitchen Manipulation",
        "suite": "libero_goal",
        "task_id": 9,
        "description": (
            "Objects: black bowl, cream cheese, wine bottle, plate. "
            "Fixtures/targets: wooden cabinet drawers/top, flat stove, "
            "wine rack, stove-front table region."
        ),
        "examples": [
            "Put the black bowl on the stove.",
            "Put the wine bottle on top of the cabinet.",
            "Put the cream cheese on the black bowl.",
            "Put the black bowl in the top drawer.",
            "Open the middle drawer.",
            "Turn on the stove.",
            "Push the plate to the front of the stove.",
        ],
    },

    "B": {
        "name": "Living Room Object Selection",
        "suite": "libero_10",
        "task_id": 0,
        "description": (
            "Objects: alphabet soup, cream cheese, tomato sauce, ketchup, "
            "orange juice, milk, butter. Target: basket."
        ),
        "examples": [
            "Put the milk in the basket.",
            "Place the ketchup inside the basket.",
            "Move the butter into the basket.",
            "Put the milk and butter in the basket.",
        ],
    },

    "C": {
        "name": "Study Desk Spatial Task",
        "suite": "libero_10",
        "task_id": 5,
        "description": (
            "Objects: black book, white-yellow mug. "
            "Targets: front/back/left/right compartments of desk caddy, "
            "plus the table region to the right of the caddy."
        ),
        "examples": [
            "Put the black book in the back compartment of the caddy.",
            "Place the mug in the left compartment of the caddy.",
            "Move the black book to the right of the desk caddy.",
        ],
    },
}


# ============================================================
# Text helpers
# ============================================================

def normalize_text(text: str) -> str:
    text = text.lower().replace("-", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_any(text: str, aliases: list[str]) -> bool:
    padded = f" {text} "

    for alias in aliases:
        alias_n = normalize_text(alias)

        if f" {alias_n} " in padded:
            return True

    return False


def find_all_entities(
    text: str,
    entity_aliases: dict[str, list[str]],
) -> list[str]:

    found = []

    for canonical, aliases in entity_aliases.items():

        if contains_any(text, aliases):
            found.append(canonical)

    return found


def clean_instruction(text: str) -> str:

    # Parentheses would interfere with the BDDL S-expression.
    text = text.replace("(", "").replace(")", "")

    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        raise ValueError("Instruction is empty.")

    return text


# ============================================================
# Scene-specific parsers
# ============================================================

def parse_scene_a(instruction: str):

    text = normalize_text(instruction)

    object_aliases = {
        "akita_black_bowl_1": [
            "black bowl",
            "bowl",
        ],

        "cream_cheese_1": [
            "cream cheese",
            "cheese",
        ],

        "wine_bottle_1": [
            "wine bottle",
            "bottle",
        ],

        "plate_1": [
            "plate",
        ],
    }


    # --------------------------------------------------------
    # Turn on stove
    # --------------------------------------------------------

    if "turn on" in text and "stove" in text:

        return (
            [
                "(Turnon flat_stove_1)"
            ],

            [
                "flat_stove_1"
            ],

            [
                "Turn on the flat stove."
            ],
        )


    # --------------------------------------------------------
    # Cabinet drawer
    # --------------------------------------------------------

    drawer_map = {

        "top":
            "wooden_cabinet_1_top_region",

        "middle":
            "wooden_cabinet_1_middle_region",

        "bottom":
            "wooden_cabinet_1_bottom_region",
    }


    drawer_level = None

    for level in (
        "top",
        "middle",
        "bottom",
    ):

        if (
            level in text
            and "drawer" in text
        ):

            drawer_level = level
            break


    # --------------------------------------------------------
    # Open / close drawer
    #
    # Also supports:
    # Open the top drawer and put the bowl inside.
    # --------------------------------------------------------

    if (
        drawer_level
        and (
            "open" in text
            or "close" in text
        )
    ):

        drawer_region = drawer_map[
            drawer_level
        ]

        goals = []
        explanation = []
        interests = [
            drawer_region
        ]


        if "open" in text:

            goals.append(
                f"(Open {drawer_region})"
            )

            explanation.append(
                f"Open the {drawer_level} drawer."
            )

        elif "close" in text:

            goals.append(
                f"(Close {drawer_region})"
            )

            explanation.append(
                f"Close the {drawer_level} drawer."
            )


        objects = find_all_entities(
            text,
            object_aliases,
        )


        motion_words = (
            "put",
            "place",
            "move",
            "inside",
            "into",
            " in ",
        )


        if (
            objects
            and any(
                word in f" {text} "
                for word in motion_words
            )
        ):

            if len(objects) > 1:

                raise ValueError(
                    "Scene A combined drawer task currently "
                    "supports one object only."
                )


            obj = objects[0]

            goals.append(
                f"(In {obj} {drawer_region})"
            )

            interests.insert(
                0,
                obj,
            )

            explanation.append(
                f"Place {obj} inside the "
                f"{drawer_level} drawer."
            )


        return (
            goals,
            interests,
            explanation,
        )


    # --------------------------------------------------------
    # Pick / place / move tasks
    # --------------------------------------------------------

    objects = find_all_entities(
        text,
        object_aliases,
    )


    if not objects:

        raise ValueError(
            "No manipulable object recognized. "
            "Use: black bowl, cream cheese, "
            "wine bottle, or plate."
        )


    # Pick the earliest mentioned object as source.
    # This handles:
    #
    # Put the cream cheese on the black bowl.
    #
    # source = cream cheese
    # target = black bowl

    source_candidates = []

    for canonical, aliases in object_aliases.items():

        for alias in aliases:

            alias_n = normalize_text(alias)

            pos = text.find(alias_n)

            if pos >= 0:

                source_candidates.append(
                    (
                        pos,
                        canonical,
                        alias_n,
                    )
                )


    source_candidates.sort()

    source = source_candidates[0][1]


    # --------------------------------------------------------
    # Detect target
    # --------------------------------------------------------

    if (
        "front of the stove" in text
        or "in front of the stove" in text
    ):

        target = (
            "main_table_stove_front_region"
        )

        predicate = "On"

        target_label = (
            "the table region in front "
            "of the stove"
        )


    elif (
        "top of the cabinet" in text
        or "on top of the cabinet" in text
        or "cabinet top" in text
    ):

        target = (
            "wooden_cabinet_1_top_side"
        )

        predicate = "On"

        target_label = (
            "the top surface of the cabinet"
        )


    elif drawer_level:

        target = drawer_map[
            drawer_level
        ]

        predicate = "In"

        target_label = (
            f"the {drawer_level} drawer"
        )


    elif (
        "wine rack" in text
        or re.search(r"\brack\b", text)
    ):

        target = (
            "wine_rack_1_top_region"
        )

        predicate = "On"

        target_label = (
            "the wine rack"
        )


    elif "stove" in text:

        target = (
            "flat_stove_1_cook_region"
        )

        predicate = "On"

        target_label = (
            "the stove cook region"
        )


    elif (
        "plate" in text
        and source != "plate_1"
    ):

        target = "plate_1"

        predicate = "On"

        target_label = "the plate"


    elif (
        (
            "black bowl" in text
            or re.search(r"\bbowl\b", text)
        )

        and source
        != "akita_black_bowl_1"
    ):

        target = (
            "akita_black_bowl_1"
        )

        predicate = "On"

        target_label = (
            "the black bowl"
        )


    else:

        raise ValueError(
            "No valid target recognized for Scene A. "
            "Try: plate, black bowl, stove, wine rack, "
            "top/middle/bottom drawer, top of cabinet, "
            "or front of stove."
        )


    if source == target:

        raise ValueError(
            "Source object and target "
            "are the same object."
        )


    goal = (
        f"({predicate} "
        f"{source} "
        f"{target})"
    )


    return (

        [
            goal
        ],

        [
            source,
            target,
        ],

        [
            f"{predicate}: "
            f"{source} -> "
            f"{target_label}."
        ],
    )


# ============================================================
# Scene B
# ============================================================

def parse_scene_b(instruction: str):

    text = normalize_text(
        instruction
    )


    if "basket" not in text:

        raise ValueError(
            "Scene B tasks must use "
            "the basket as the target."
        )


    object_aliases = {

        "alphabet_soup_1": [
            "alphabet soup",
            "soup",
        ],

        "cream_cheese_1": [
            "cream cheese",
        ],

        "tomato_sauce_1": [
            "tomato sauce",
        ],

        "ketchup_1": [
            "ketchup",
        ],

        "orange_juice_1": [
            "orange juice",
            "juice",
        ],

        "milk_1": [
            "milk",
        ],

        "butter_1": [
            "butter",
        ],
    }


    objects = find_all_entities(
        text,
        object_aliases,
    )


    if not objects:

        raise ValueError(
            "No Scene B object recognized. "
            "Use: alphabet soup, cream cheese, "
            "tomato sauce, ketchup, orange juice, "
            "milk, or butter."
        )


    target = (
        "basket_1_contain_region"
    )


    goals = [

        f"(In {obj} {target})"

        for obj in objects
    ]


    interests = (

        objects
        + [
            target
        ]
    )


    explanation = [

        f"In: {obj} -> basket."

        for obj in objects
    ]


    return (
        goals,
        interests,
        explanation,
    )


# ============================================================
# Scene C
# ============================================================

def parse_scene_c(instruction: str):

    text = normalize_text(
        instruction
    )


    object_aliases = {

        "black_book_1": [
            "black book",
            "book",
        ],

        "white_yellow_mug_1": [
            "white yellow mug",
            "mug",
            "cup",
        ],
    }


    objects = find_all_entities(
        text,
        object_aliases,
    )


    if not objects:

        raise ValueError(
            "No Scene C object recognized. "
            "Use: black book or mug."
        )


    # --------------------------------------------------------
    # Optional:
    # object to the right of the desk caddy
    # --------------------------------------------------------

    right_of_caddy_phrases = [

        "right of the desk caddy",

        "right of the caddy",

        "to the right of the desk caddy",

        "to the right of the caddy",
    ]


    if any(
        phrase in text
        for phrase in right_of_caddy_phrases
    ):

        target = (
            "study_table_desk_caddy_right_region"
        )


        goals = [

            f"(On {obj} {target})"

            for obj in objects
        ]


        interests = (

            objects
            + [
                target
            ]
        )


        explanation = [

            f"On: {obj} -> "
            "table region right of desk caddy."

            for obj in objects
        ]


        return (
            goals,
            interests,
            explanation,
        )


    # --------------------------------------------------------
    # Caddy compartments
    # --------------------------------------------------------

    compartment_map = {

        "front":
            "desk_caddy_1_front_contain_region",

        "back":
            "desk_caddy_1_back_contain_region",

        "left":
            "desk_caddy_1_left_contain_region",

        "right":
            "desk_caddy_1_right_contain_region",
    }


    mentioned = [

        direction

        for direction
        in compartment_map

        if (
            direction in text
            and "compartment" in text
        )
    ]


    if len(mentioned) == 0:

        raise ValueError(
            "No caddy compartment recognized. "
            "Use front/back/left/right compartment."
        )


    if len(mentioned) > 1:

        raise ValueError(
            "This classroom script supports "
            "one compartment per instruction. "
            "Use one spatial target at a time."
        )


    direction = mentioned[0]

    target = (
        compartment_map[
            direction
        ]
    )


    goals = [

        f"(In {obj} {target})"

        for obj in objects
    ]


    interests = (

        objects
        + [
            target
        ]
    )


    explanation = [

        f"In: {obj} -> "
        f"{direction} compartment."

        for obj in objects
    ]


    return (
        goals,
        interests,
        explanation,
    )


PARSERS = {

    "A":
        parse_scene_a,

    "B":
        parse_scene_b,

    "C":
        parse_scene_c,
}


# ============================================================
# BDDL helpers
# ============================================================

def find_section_span(
    text: str,
    section_name: str,
) -> tuple[int, int]:

    marker = (
        f"(:{section_name}"
    )

    start = text.find(
        marker
    )


    if start < 0:

        raise ValueError(
            f"Section {marker} "
            "not found in base BDDL."
        )


    depth = 0
    started = False


    for i in range(
        start,
        len(text),
    ):

        char = text[i]


        if char == "(":

            depth += 1
            started = True


        elif char == ")":

            depth -= 1


            if (
                started
                and depth == 0
            ):

                return (
                    start,
                    i + 1,
                )


    raise ValueError(
        f"Could not find end "
        f"of section {marker}."
    )


def replace_section(
    text: str,
    section_name: str,
    new_block: str,
) -> str:

    start, end = find_section_span(
        text,
        section_name,
    )


    return (

        text[:start]
        + new_block
        + text[end:]
    )


def make_language_block(
    instruction: str,
) -> str:

    return (
        f"(:language {instruction})"
    )


def make_interest_block(
    interests: list[str],
) -> str:

    unique = list(
        dict.fromkeys(
            interests
        )
    )


    lines = [
        "(:obj_of_interest"
    ]


    lines.extend(

        f"    {name}"

        for name in unique
    )


    lines.append(
        "  )"
    )


    return "\n".join(
        lines
    )


def make_goal_block(
    goals: list[str],
) -> str:

    lines = [

        "(:goal",

        "    (And",
    ]


    lines.extend(

        f"        {goal}"

        for goal in goals
    )


    lines.extend(
        [
            "    )",
            "  )",
        ]
    )


    return "\n".join(
        lines
    )


def slugify(
    text: str,
    max_len: int = 80,
) -> str:

    slug = (
        normalize_text(text)
        .replace(
            " ",
            "_",
        )
    )


    slug = re.sub(
        r"[^a-z0-9_]",
        "",
        slug,
    )


    slug = (
        slug.strip("_")
        or "custom_task"
    )


    return (
        slug[:max_len]
        .rstrip("_")
    )


# ============================================================
# Scene helpers
# ============================================================

def get_base_scene(
    scene_key: str,
):

    cfg = SCENES[
        scene_key
    ]


    suite = (
        benchmark
        .get_benchmark_dict()[
            cfg["suite"]
        ]()
    )


    task = suite.get_task(
        cfg["task_id"]
    )


    bddl_path = os.path.join(

        get_libero_path(
            "bddl_files"
        ),

        task.problem_folder,

        task.bddl_file,
    )


    return (
        cfg,
        suite,
        task,
        Path(bddl_path),
    )


# ============================================================
# Create BDDL
# ============================================================

def create_custom_bddl(
    scene_key: str,
    instruction: str,
    goals: list[str],
    interests: list[str],
) -> Path:

    (
        cfg,
        suite,
        task,
        base_bddl_path,
    ) = get_base_scene(
        scene_key
    )


    text = (
        base_bddl_path
        .read_text(
            encoding="utf-8"
        )
    )


    text = replace_section(

        text,

        "language",

        make_language_block(
            instruction
        ),
    )


    text = replace_section(

        text,

        "obj_of_interest",

        make_interest_block(
            interests
        ),
    )


    text = replace_section(

        text,

        "goal",

        make_goal_block(
            goals
        ),
    )


    scene_dir = (

        OUTPUT_ROOT
        / f"scene_{scene_key}"
    )


    scene_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


    filename = (

        slugify(
            instruction
        )
        + ".bddl"
    )


    output_path = (

        scene_dir
        / filename
    )


    output_path.write_text(
        text,
        encoding="utf-8",
    )


    # Save metadata for the future
    # SmolVLA runner.

    metadata = {

        "scene":
            scene_key,

        "scene_name":
            cfg["name"],

        "base_suite":
            cfg["suite"],

        "base_task_id":
            cfg["task_id"],

        "instruction":
            instruction,

        "goals":
            goals,

        "obj_of_interest":
            interests,

        "bddl_file":
            str(output_path),
    }


    metadata_path = (
        output_path
        .with_suffix(".json")
    )


    metadata_path.write_text(

        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),

        encoding="utf-8",
    )


    return output_path


# ============================================================
# Validate custom task
# ============================================================

def validate_and_preview(
    scene_key: str,
    custom_bddl_path: Path,
):

    (
        cfg,
        suite,
        task,
        _,
    ) = get_base_scene(
        scene_key
    )


    # --------------------------------------------------------
    # 1. Parse BDDL
    # --------------------------------------------------------

    parsed = (
        BDDLUtils
        .robosuite_parse_problem(
            str(
                custom_bddl_path
            )
        )
    )


    print(
        "\n"
        + "=" * 72
    )

    print(
        "CUSTOM TASK PARSED SUCCESSFULLY"
    )

    print(
        "=" * 72
    )


    print(
        "\nLanguage:"
    )

    print(
        parsed[
            "language_instruction"
        ]
    )


    print(
        "\nGoal:"
    )


    for goal in parsed[
        "goal_state"
    ]:

        print(
            " ",
            goal,
        )


    # --------------------------------------------------------
    # 2. Create environment
    # --------------------------------------------------------

    env = OffScreenRenderEnv(

        bddl_file_name=str(
            custom_bddl_path
        ),

        camera_names=[
            "agentview",
            "robot0_eye_in_hand",
        ],

        camera_heights=
            CAMERA_HEIGHT,

        camera_widths=
            CAMERA_WIDTH,
    )


    env.seed(
        0
    )


    env.reset()


    # We changed only:
    #
    # language
    # obj_of_interest
    # goal
    #
    # Objects / fixtures / init layout
    # are unchanged.
    #
    # Therefore the original fixed
    # official init state is compatible.

    init_states = (
        suite
        .get_task_init_states(
            cfg[
                "task_id"
            ]
        )
    )


    obs = env.set_init_state(
        init_states[0]
    )


    initial_success = bool(
        env.check_success()
    )


    print(
        "\nInitial goal already satisfied?:",
        initial_success,
    )


    if initial_success:

        print(
            "\nWARNING:"
        )

        print(
            "This task is already successful at reset."
        )

        print(
            "Choose another goal; otherwise the "
            "experiment has little meaning."
        )


    # --------------------------------------------------------
    # 3. Save preview
    # --------------------------------------------------------

    image = np.flipud(

        obs[
            "agentview_image"
        ]
    )


    preview_path = (
        custom_bddl_path
        .with_suffix(
            ".png"
        )
    )


    plt.imsave(
        preview_path,
        image,
    )


    print(
        "\nCustom BDDL:"
    )

    print(
        custom_bddl_path
    )


    print(
        "\nMetadata:"
    )

    print(
        custom_bddl_path
        .with_suffix(
            ".json"
        )
    )


    print(
        "\nPreview image:"
    )

    print(
        preview_path
    )


    if SHOW_IMAGE:

        plt.figure(
            figsize=(8, 8)
        )


        plt.imshow(
            image
        )


        plt.title(
            f"Scene {scene_key} - Custom Task\n"
            f"{parsed['language_instruction']}"
        )


        plt.axis(
            "off"
        )


        plt.tight_layout()


        plt.show()


    env.close()


    return initial_success


# ============================================================
# User interface
# ============================================================

def print_scene_menu():

    print(
        "=" * 72
    )

    print(
        "LIBERO CUSTOM TASK BUILDER"
    )

    print(
        "=" * 72
    )


    for key in (
        "A",
        "B",
        "C",
    ):

        cfg = SCENES[
            key
        ]


        print(
            f"\nScene {key}: "
            f"{cfg['name']}"
        )


        print(
            cfg[
                "description"
            ]
        )


        print(
            "Examples:"
        )


        for example in cfg[
            "examples"
        ]:

            print(
                "  -",
                example,
            )


def main():

    print_scene_menu()


    scene_key = input(
        "\nChoose Scene [A/B/C]: "
    ).strip().upper()


    if scene_key not in SCENES:

        raise ValueError(
            "Scene must be A, B, or C."
        )


    print(
        "\nSelected:"
    )


    print(
        f"Scene {scene_key} - "
        f"{SCENES[scene_key]['name']}"
    )


    print(
        "\nEnter ONE English task instruction."
    )


    print(
        "Use objects and targets that "
        "already exist in this scene."
    )


    raw_instruction = input(
        "\nInstruction: "
    )


    instruction = clean_instruction(
        raw_instruction
    )


    parser = PARSERS[
        scene_key
    ]


    (
        goals,
        interests,
        explanation,
    ) = parser(
        instruction
    )


    print(
        "\n"
        + "=" * 72
    )

    print(
        "TASK INTERPRETATION"
    )

    print(
        "=" * 72
    )


    print(
        "\nInstruction:"
    )

    print(
        instruction
    )


    print(
        "\nInterpreted goal(s):"
    )


    for line in explanation:

        print(
            " -",
            line,
        )


    print(
        "\nGenerated BDDL predicate(s):"
    )


    for goal in goals:

        print(
            " ",
            goal,
        )


    answer = input(
        "\nGenerate and validate this task? [y/N]: "
    ).strip().lower()


    if answer != "y":

        print(
            "Cancelled."
        )

        return


    custom_bddl_path = (
        create_custom_bddl(

            scene_key=
                scene_key,

            instruction=
                instruction,

            goals=
                goals,

            interests=
                interests,
        )
    )


    validate_and_preview(

        scene_key=
            scene_key,

        custom_bddl_path=
            custom_bddl_path,
    )


    print(
        "\n"
        + "=" * 72
    )

    print(
        "DONE"
    )

    print(
        "=" * 72
    )


    print(
        "\nThis script has created and "
        "validated the task definition only."
    )


    print(
        "It has NOT run SmolVLA yet."
    )


if __name__ == "__main__":
    main()
