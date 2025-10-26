import { defineConfig } from "vite";
import dotenv from 'dotenv';
import tailwindcss from "@tailwindcss/vite";
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import YAML from 'yaml';
import { processImages } from './src/image-preprocess.mjs';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const inputDir = path.join(__dirname, '/assets/images');
const outputDir = path.join(__dirname, '/assets/images-processed');
const siteConfigPath = path.join(__dirname, 'config.yaml');
const generatedThemeCssPath = path.join(__dirname, 'assets/css/generated.daisyui.css');

const loadSiteConfig = () => {
  try {
    const raw = fs.readFileSync(siteConfigPath, 'utf8');
    return YAML.parse(raw) || {};
  } catch (err) {
    console.error('[config] Unable to read config.yaml', err);
    return {};
  }
};

const generateDaisyUiThemeFile = () => {
  const siteConfig = loadSiteConfig();
  const themeConfig = siteConfig.theme || {};

  const defaultTheme = typeof themeConfig.default === 'string' ? themeConfig.default.trim() : '';

  const includeRaw = Array.isArray(themeConfig.include)
    ? themeConfig.include
    : themeConfig.include
    ? [themeConfig.include]
    : [];

  const seenNames = new Set();
  const names = [];
  if (defaultTheme) {
    const trimmed = defaultTheme.trim();
    if (trimmed) {
      seenNames.add(trimmed);
      names.push(trimmed);
    }
  }
  includeRaw.forEach((entry) => {
    if (typeof entry !== 'string') return;
    const trimmed = entry.trim();
    if (!trimmed || seenNames.has(trimmed)) return;
    seenNames.add(trimmed);
    names.push(trimmed);
  });

  const formatValue = (value) => {
    if (typeof value === 'boolean') {
      return value ? 'true' : 'false';
    }
    if (typeof value === 'number') {
      return String(value);
    }
    if (typeof value === 'string') {
      if (value === '') {
        return '""';
      }
      if (/\s|;|:|"/.test(value)) {
        return JSON.stringify(value);
      }
      return value;
    }
    return JSON.stringify(value);
  };

  const blocks = [];

  if (names.length) {
    const joined = names.map((name) => JSON.stringify(name)).join(', ');
    blocks.push(`@plugin "daisyui" {\n  themes: (${joined});\n}`);
  } else {
    blocks.push('@plugin "daisyui" {\n  themes: all;\n}');
  }

  const customRaw = themeConfig.custom;
  if (customRaw && typeof customRaw === 'object') {
    for (const [name, values] of Object.entries(customRaw)) {
      if (!name || typeof values !== 'object' || values === null) {
        continue;
      }

      const lines = ['@plugin "daisyui/theme" {'];
      const seenKeys = new Set();

      const emitKey = (key, value) => {
        if (seenKeys.has(key)) return;
        seenKeys.add(key);
        lines.push(`  ${key}: ${formatValue(value)};`);
      };

      emitKey('name', Object.prototype.hasOwnProperty.call(values, 'name') ? values.name : name);

      if (Object.prototype.hasOwnProperty.call(values, 'default')) {
        emitKey('default', values.default);
      }

      for (const [key, value] of Object.entries(values)) {
        emitKey(key, value);
      }

      if (!seenKeys.has('default')) {
        const isDefault = defaultTheme && defaultTheme === name;
        emitKey('default', isDefault);
      }

      lines.push('}');
      blocks.push(lines.join('\n'));
    }
  }

  fs.mkdirSync(path.dirname(generatedThemeCssPath), { recursive: true });
  fs.writeFileSync(generatedThemeCssPath, `${blocks.join('\n\n')}\n`, 'utf8');
};

processImages(inputDir, outputDir).catch(e =>
  console.error('[images] initial processing failed', e)
);

generateDaisyUiThemeFile();

const pythonexecutable = process.env.PY_EXECUTABLE;

if (!pythonexecutable) {
  throw new Error('Need to set PY_EXECUTABLE environment variable to run build.');
}

const ensurePythonRequirements = () => {
  const requirementsPath = path.join(__dirname, 'requirements.txt');
  try {
    console.log('Installing python dependencies...');
    execSync(`${pythonexecutable} -m pip install -r "${requirementsPath}"`, { stdio: 'inherit' });
  } catch (e) {
    console.error('Failed to install Python dependencies. Verify interpreter path.', e);
  }
};

ensurePythonRequirements();


const py_build_plugin = () => {
  let ready = false;

  const syntaxCssPath = './assets/css/syntax.css';
  const syntaxCssDir = path.dirname(syntaxCssPath);
  const syntaxTheme = process.env.PYGMENTIZE_THEME || 'native';
  fs.mkdirSync(syntaxCssDir, { recursive: true });
  try {
    console.log(`Generating syntax.css with theme "${syntaxTheme}"...`);
    execSync(`pygmentize -S ${syntaxTheme} -f html > ${syntaxCssPath}`);
    console.log('Generated syntax.css');
  } catch (e) {
    console.error('Failed to generate syntax.css.', e);
  }

  const handleExit = () => {
    console.log('\nCleaning up build files...');
    try {
      const output = execSync(`${pythonexecutable} src/main.py --clean`);
      console.log(output.toString().trim());
    } catch (e) {
      console.error("Cleanup script failed:", e);
    }
    process.exit();
  };

  process.on('SIGINT', handleExit);

  return {
    name: 'builder-ssg',
    configureServer(server) {
      const regenerateThemes = () => {
        try {
          generateDaisyUiThemeFile();
        } catch (e) {
          console.error('[theme] failed to regenerate DaisyUI theme file', e);
        }
      };

      const build = (file = null) => {
        const command = file
          ? `${pythonexecutable} src/main.py --file ${file}`
          : `${pythonexecutable} src/main.py`;

        try {
          const output = execSync(command);
          console.log(output.toString().trim());

          server.ws.send({ type: 'full-reload', path: "*" });
          ready = true;
        } catch (e) {
          console.error("Script failed to update: ", e);
        }
      };

      build();

      server.watcher.on('all', (event, filePath) => {
        if (!ready) {
          return;
        }

        if (filePath.endsWith('config.yaml')) {
          regenerateThemes();
          build();
          return;
        }

        if (filePath.includes('/content/') || filePath.includes('/templates/')) {
          if (event === 'change') {
            const buildTarget = filePath.includes('/templates/') ? null : filePath;
            build(buildTarget);
          } else if (event === 'add' || event === 'unlink') {
            build();
          }
        }
        if (event === 'change' && filePath.includes('/assets/css/')) {
          build();
        }
        if (event === 'unlink') { // if html files are deleted
          build();
        }
      });
    },
  };
};


export default defineConfig({
  plugins: [
    py_build_plugin(),
    tailwindcss(),
  ],
  build: {
    outDir: './dist',
  },
});