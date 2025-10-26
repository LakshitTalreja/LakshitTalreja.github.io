import os
import yaml
import markdown
from markdown.extensions.toc import TocExtension
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import argparse
import shutil
import hashlib
import json
import re
from html import escape
from html.parser import HTMLParser
import dotenv

dotenv.load_dotenv()

PYGMENTIZE_THEME = os.getenv("PYGMENTIZE_THEME", "native")
TEMPLATE_DIR = "templates"
CONFIG_FILE = "config.yaml"
OUTPUT_DIR = "."
IMAGES_DIR = "assets/images"
CONTENT_DIR = "content"
POSTS_DIR = "content/posts"

PAGE_SLUG_CACHE = ".cache/page-slugs.json"
IMAGE_MANIFEST_PATH = ".cache/image-manifest.json"
GENERATED_THEME_PATH = "assets/css/generated.daisyui.css"


def load_previous_slugs():
    try:
        with open(PAGE_SLUG_CACHE, "r") as f:
            return set(json.load(f))
    except:
        return set()


def save_current_slugs(slugs):
    os.makedirs(os.path.dirname(PAGE_SLUG_CACHE), exist_ok=True)
    with open(PAGE_SLUG_CACHE, "w") as f:
        json.dump(sorted(slugs), f)


def clean_output(directory):
    print("Cleaning old build files...")
    preserved_roots = {
        ".git",
        ".github",
        ".cache",
        "assets",
        "content",
        "node_modules",
        "src",
        "templates",
    }
    generated_roots = {"blog", "tags", "posts"}

    removed_any = False
    for root, _, files in os.walk(directory, topdown=False):
        rel_root = os.path.relpath(root, directory)
        if rel_root == ".":
            rel_root = ""
        top_level = rel_root.split(os.sep)[0] if rel_root else ""

        if top_level in preserved_roots:
            continue

        for filename in files:
            delete_file = False
            if top_level in generated_roots:
                delete_file = True
            elif filename == "index.html" or filename.endswith(".xml"):
                delete_file = True

            if delete_file:
                file_path = os.path.join(root, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    removed_any = True
                    print(f"Deleted: {file_path}")

        if rel_root and top_level not in preserved_roots and not os.listdir(root):
            os.rmdir(root)
            removed_any = True
            print(f"Deleted empty directory: {root}")

    if not removed_any:
        print("No generated files found to delete.")


def has_file_changed(filepath, cache_dir=".cache"):
    os.makedirs(cache_dir, exist_ok=True)
    rel = os.path.relpath(filepath)
    file_hash = hashlib.md5(open(filepath, "rb").read()).hexdigest()
    safe_name = rel.replace(os.sep, "__") + ".hash"
    cache_file = os.path.join(cache_dir, safe_name)

    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cached_hash = f.read().strip()
        if cached_hash == file_hash:
            return False

    with open(cache_file, "w") as f:
        f.write(file_hash)
    return True


def normalize_theme_config(config):
    theme_config = config.get("theme")

    if isinstance(theme_config, str):
        normalized = {"default": theme_config}
    elif isinstance(theme_config, dict):
        normalized = dict(theme_config)
    else:
        normalized = {}

    default_theme = (
        normalized.get("default")
        or normalized.get("preset")
        or normalized.get("name")
        or "dracula"
    )
    normalized["default"] = default_theme

    include_candidates = normalized.get("include") or normalized.get("presets")
    if not include_candidates:
        include_candidates = []
    elif not isinstance(include_candidates, list):
        include_candidates = [include_candidates]

    ordered = []
    seen = set()
    for entry in include_candidates:
        if not entry or entry in seen:
            continue
        ordered.append(entry)
        seen.add(entry)
    if default_theme and default_theme not in seen:
        ordered.insert(0, default_theme)
    normalized["include"] = ordered

    config["theme"] = normalized
    return normalized


def write_theme_file(config, output_path=GENERATED_THEME_PATH):
    theme = config.get("theme") or {}
    include = theme.get("include") or []
    custom_raw = theme.get("custom")

    def format_value(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, str):
            if not value:
                return "\"\""
            if re.search(r"[\s;:\"]", value):
                return json.dumps(value)
            return value
        return json.dumps(value)

    names = []
    seen = set()
    for entry in include:
        if not entry or entry in seen:
            continue
        names.append(entry)
        seen.add(entry)

    css_blocks = []

    if names:
        joined_names = ", ".join(json.dumps(name) for name in names)
        css_blocks.append(
            '@plugin "daisyui" {\n  themes: (' + joined_names + ');\n}'
        )
    else:
        css_blocks.append('@plugin "daisyui" {\n  themes: all;\n}')

    custom_items = custom_raw.items() if isinstance(custom_raw, dict) else []
    for name, values in custom_items:
        if not name or not isinstance(values, dict):
            continue

        value_pairs = []
        seen_keys = set()

        if "name" in values:
            value_pairs.append(("name", values["name"]))
            seen_keys.add("name")
        else:
            value_pairs.append(("name", name))
            seen_keys.add("name")

        if "default" in values:
            value_pairs.append(("default", values["default"]))
            seen_keys.add("default")
        else:
            value_pairs.append(("default", theme.get("default") == name))
            seen_keys.add("default")

        for key, value in values.items():
            if key in seen_keys:
                continue
            value_pairs.append((key, value))
            seen_keys.add(key)

        lines = ["@plugin \"daisyui/theme\" {"]
        for key, value in value_pairs:
            lines.append(f"  {key}: {format_value(value)};")
        lines.append("}")
        css_blocks.append("\n".join(lines))

    css_content = "\n\n".join(css_blocks) + "\n"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(css_content)


MARKDOWN_EXTENSIONS = [
    "fenced_code",
    "codehilite",
    "footnotes",
    "tables",
    "attr_list",
    "sane_lists",
    "md_in_html",
    TocExtension(permalink=True),
]

MARKDOWN_EXTENSION_CONFIGS = {
    "codehilite": {
        "guess_lang": False,
        "noclasses": False,
        "pygments_style": PYGMENTIZE_THEME,
    },
}


def build_markdown():
    return markdown.Markdown(
        extensions=MARKDOWN_EXTENSIONS, extension_configs=MARKDOWN_EXTENSION_CONFIGS
    )


def load_templates(env, template_dir=TEMPLATE_DIR, allowed_extensions=(".html", ".jinja", ".jinja2", ".j2")):
    templates = {}
    for root, _, files in os.walk(template_dir):
        for filename in files:
            if allowed_extensions and not filename.endswith(allowed_extensions):
                continue
            rel_path = os.path.relpath(os.path.join(root, filename), template_dir)
            rel_path = rel_path.replace(os.sep, "/")
            template = env.get_template(rel_path)
            base_name = os.path.splitext(filename)[0]
            rel_without_ext = os.path.splitext(rel_path)[0]
            for key in (rel_path, rel_without_ext, base_name):
                if key not in templates:
                    templates[key] = template
    return templates


def parse_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            file_content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found - {filepath}")
        return None, None

    if file_content.startswith("---"):
        try:
            parts = file_content.split("---", 2)
            page_config = yaml.safe_load(parts[1]) or {}
            markdown_data = parts[2]
        except (IndexError, yaml.YAMLError) as e:
            print(f"Error parsing YAML frontmatter in {filepath}: {e}")
            page_config = {}
            markdown_data = file_content
    else:
        page_config = {}
        markdown_data = file_content

    md = build_markdown()
    html_data = md.convert(markdown_data)
    md.reset()

    slug = os.path.splitext(os.path.basename(filepath))[0]
    rel_posts = os.path.normpath(POSTS_DIR)
    if os.path.normpath(filepath).startswith(rel_posts):
        page_config["url"] = f"/posts/{slug}"
    elif slug == "index":
        page_config["url"] = "/"
    else:
        page_config["url"] = f"/{slug}"

    # Normalize date to YYYY-MM-DD string
    if "date" in page_config and page_config["date"]:
        if isinstance(page_config["date"], datetime):
            page_config["date"] = page_config["date"].strftime("%Y-%m-%d")
        else:
            try:
                parsed = datetime.fromisoformat(str(page_config["date"]))
                page_config["date"] = parsed.strftime("%Y-%m-%d")
            except Exception:
                pass

    return page_config, html_data


def tag_pages(tag_template, site_config, tags=None, image_manifest=None):
    tags = tags or {}
    tags_dir = os.path.join(OUTPUT_DIR, "tags")
    os.makedirs(tags_dir, exist_ok=True)

    for tag_name, posts_with_tag in tags.items():
        posts_with_tag.sort(
            key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"), reverse=True
        )
        tag_page_html = tag_template.render(
            site=site_config,
            tag_name=tag_name,
            posts=posts_with_tag,
            page={"title": f"Tag: {tag_name}"},
        )
        tag_page_html = replace_images_with_processed(tag_page_html, image_manifest)
        output_path = os.path.join(tags_dir, f"{tag_name}.html")
        with open(output_path, "w") as f:
            f.write(tag_page_html)
        print(f"Generated tag page: tags/{tag_name}.html")


def render_page(
    page_config,
    html_data,
    site_config,
    templates,
    image_manifest=None,
    all_posts=None,
):
    layout = page_config.get("layout")
    if layout not in templates:
        available = ", ".join(sorted(templates.keys())) or "none"
        print(
            f"Error: Template '{layout}' not found. Available templates: {available}. Skipping build."
        )
        return

    template = templates[layout]

    render_details = {"site": site_config, "page": page_config, "content": html_data}
    if layout == "blog" and all_posts is not None:
        render_details["posts"] = all_posts

    final_html = template.render(render_details)
    final_html = replace_images_with_processed(final_html, image_manifest)

    if page_config["url"] == "/":
        output_path = os.path.join(OUTPUT_DIR, "index.html")
    else:
        output_path = os.path.join(
            OUTPUT_DIR, page_config["url"].lstrip("/"), "index.html"
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(final_html)
    print(
        f"Generated: {page_config['url'] if page_config['url'] != '/' else '/index.html'}"
    )



def load_image_manifest(path=IMAGE_MANIFEST_PATH):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Warning: Unable to parse image manifest {path}: {exc}")
        return {}


def _render_attributes(attrs):
    parts = []
    for name, value in attrs:
        if value is None:
            parts.append(f" {name}")
        else:
            parts.append(f' {name}="{escape(str(value), quote=True)}"')
    return "".join(parts)


def _build_picture_element(attrs, manifest_entry):
    if not manifest_entry:
        return None

    attrs_dict = {name.lower(): value for name, value in attrs}
    sizes_value = attrs_dict.get("data-img-sizes") or attrs_dict.get("sizes") or "100vw"

    format_priority = ["avif", "webp", "jpg", "jpeg", "png"]
    fallback_priority = ["jpg", "jpeg", "png", "webp", "avif"]
    mime_overrides = {"jpg": "image/jpeg", "jpeg": "image/jpeg"}

    sources = []
    for fmt in format_priority:
        variants = manifest_entry.get(fmt)
        if not variants:
            continue
        sorted_variants = sorted(
            (v for v in variants if v.get("path") and v.get("width")),
            key=lambda item: item["width"],
        )
        if not sorted_variants:
            continue
        srcset = ", ".join(
            f"/{variant['path']} {variant['width']}w" for variant in sorted_variants
        )
        mime = mime_overrides.get(fmt, f"image/{fmt}")
        sources.append(
            f'<source type="{mime}" srcset="{srcset}" sizes="{sizes_value}">'
        )

    if not sources:
        return None

    fallback_format = next(
        (fmt for fmt in fallback_priority if manifest_entry.get(fmt)), None
    )
    if not fallback_format:
        return None

    fallback_variants = sorted(
        (
            v
            for v in manifest_entry[fallback_format]
            if v.get("path") and v.get("width")
        ),
        key=lambda item: item.get("width", 0),
    )
    if not fallback_variants:
        return None

    fallback_src = f"/{fallback_variants[-1]['path']}"
    fallback_srcset = ", ".join(
        f"/{variant['path']} {variant['width']}w" for variant in fallback_variants
    )

    filtered_attrs = [
        (name, value)
        for (name, value) in attrs
        if name.lower() not in {"src", "srcset", "sizes", "data-img-sizes"}
    ]
    fallback_attrs = [("src", fallback_src)] + filtered_attrs
    if fallback_srcset:
        fallback_attrs.append(("srcset", fallback_srcset))
    fallback_attrs.append(("sizes", sizes_value))

    img_tag = "<img{}>".format(_render_attributes(fallback_attrs))
    sources_html = "".join(sources)
    return f"<picture>{sources_html}{img_tag}</picture>"


class ImageReplacementParser(HTMLParser):
    def __init__(self, manifest):
        super().__init__(convert_charrefs=False)
        self.manifest = manifest or {}
        self.output = []

    def handle_starttag(self, tag, attrs):
        self._handle_start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle_start(tag, attrs)

    def handle_endtag(self, tag):
        self.output.append(f"</{tag}>")

    def handle_data(self, data):
        self.output.append(data)

    def handle_comment(self, data):
        self.output.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.output.append(f"<!{decl}>")

    def handle_entityref(self, name):
        self.output.append(f"&{name};")

    def handle_charref(self, name):
        self.output.append(f"&#{name};")

    def handle_pi(self, data):
        self.output.append(f"<?{data}>")

    def _handle_start(self, tag, attrs):
        if tag.lower() == "img":
            replacement = self._build_replacement(attrs)
            if replacement:
                self.output.append(replacement)
                return
        raw = self.get_starttag_text()
        if raw:
            self.output.append(raw)

    def _build_replacement(self, attrs):
        attrs_dict = {k.lower(): v for k, v in attrs}
        src = attrs_dict.get("src")
        if not src:
            return None

        normalized = src.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if "assets/images/" not in normalized:
            return None

        relative = normalized.split("assets/images/", 1)[1]
        manifest_entry = self.manifest.get(os.path.basename(relative))
        if not manifest_entry:
            return None

        return _build_picture_element(attrs, manifest_entry)

    def get_html(self):
        return "".join(self.output)


def replace_images_with_processed(html, manifest):
    if not html or not manifest:
        return html
    parser = ImageReplacementParser(manifest)
    parser.feed(html)
    parser.close()
    return parser.get_html()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    if args.clean:
        clean_output(OUTPUT_DIR)
        if os.path.exists(PAGE_SLUG_CACHE):
            os.remove(PAGE_SLUG_CACHE)
        print("generated files are deleted.")
        return

    with open(CONFIG_FILE, "r") as f:
        site_config = yaml.safe_load(f) or {}
    normalize_theme_config(site_config)
    write_theme_file(site_config)
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    templates = load_templates(env)
    image_manifest = load_image_manifest()

    if args.file:
        print(f"Change detected in {args.file}, proceeding to rebuild...")
        if not os.path.exists(args.file):

            slug = os.path.splitext(os.path.basename(args.file))[0]
            if slug != "index":
                out_dir = os.path.join(OUTPUT_DIR, slug)
                if os.path.isdir(out_dir):
                    shutil.rmtree(out_dir)
                    print(f"Removed deleted page output: {out_dir}")

            if os.path.exists(PAGE_SLUG_CACHE):
                os.remove(PAGE_SLUG_CACHE)
            return

        if not has_file_changed(args.file):
            print(
                f"No changes detected in {args.file} based on cache; rebuilding anyway."
            )

        page_data, html_content = parse_file(args.file)
        if page_data is None or html_content is None:
            return
        render_page(
            page_data,
            html_content,
            site_config,
            templates,
            image_manifest=image_manifest,
        )
    else:
        print("Running a full build...")
        sitemap_list = []
        all_posts = []
        pages = []
        tags = {}

        clean_output(OUTPUT_DIR)

        current_slugs = set()
        previous_slugs = load_previous_slugs()

        for filename in os.listdir(CONTENT_DIR):
            if filename.endswith(".md"):
                filepath = os.path.join(CONTENT_DIR, filename)
                page_data, html_content = parse_file(filepath)
                if not page_data:
                    continue
                if str(page_data.get("draft")).lower() in ("true", "1", "yes"):
                    continue
                slug = os.path.splitext(filename)[0]
                current_slugs.add(slug)
                pages.append({"data": page_data, "content": html_content})
                sitemap_list.append(page_data["url"])

        if os.path.exists(POSTS_DIR):
            for filename in os.listdir(POSTS_DIR):
                if filename.endswith(".md"):
                    filepath = os.path.join(POSTS_DIR, filename)
                    page_data, html_content = parse_file(filepath)
                    if not page_data:
                        continue
                    if str(page_data.get("draft")).lower() in ("true", "1", "yes"):
                        continue
                    slug = os.path.splitext(filename)[0]
                    current_slugs.add(f"posts/{slug}")
                    pages.append({"data": page_data, "content": html_content})
                    sitemap_list.append(page_data["url"])
                    if page_data.get("layout") == "post":
                        all_posts.append(page_data)
                        for tag in page_data.get("tags") or []:
                            tags.setdefault(tag, []).append(page_data)

        removed = previous_slugs - current_slugs
        for slug in removed:

            if slug.startswith("posts/"):
                continue
            if slug == "index":
                continue
            out_dir = os.path.join(OUTPUT_DIR, slug)
            if os.path.isdir(out_dir):
                shutil.rmtree(out_dir)
                print(f"Removed stale page directory: {out_dir}")

        save_current_slugs(current_slugs)

        all_posts.sort(
            key=lambda x: (
                datetime.strptime(x["date"], "%Y-%m-%d")
                if x.get("date")
                else datetime.min
            ),
            reverse=True,
        )
        for page in pages:
            render_page(
                page["data"],
                page["content"],
                site_config,
                templates,
                image_manifest=image_manifest,
                all_posts=all_posts,
            )

        tag_template = templates.get("tags") or templates.get("tags.html")
        if tag_template:
            tag_pages(
                tag_template,
                site_config,
                tags,
                image_manifest=image_manifest,
            )
        else:
            print("Warning: tags template not found; skipping tag page generation.")

        sitemap_template = env.get_template("sitemap.xml.j2")
        sitemap_xml = sitemap_template.render(site=site_config, pages=sitemap_list)
        with open(os.path.join(OUTPUT_DIR, "sitemap.xml"), "w") as f:
            f.write(sitemap_xml)
        print("Generated sitemap.xml")


if __name__ == "__main__":
    main()
