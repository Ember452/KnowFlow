// 从后端 openapi.json 生成 API 端点清单，供 System 页展示。
// 用法: node scripts/gen-api-list.mjs（npm run gen:api）
// 生成文件: src/generated/apiEndpoints.ts
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const specPath = resolve(__dirname, '..', '..', 'openapi.json');
const outDir = resolve(__dirname, '..', 'src', 'generated');
const outFile = resolve(outDir, 'apiEndpoints.ts');

const METHODS = new Set(['get', 'post', 'put', 'delete']);

let endpoints = [];
try {
  const spec = JSON.parse(readFileSync(specPath, 'utf8'));
  for (const [path, methods] of Object.entries(spec.paths ?? {})) {
    for (const [method, op] of Object.entries(methods)) {
      if (!METHODS.has(method)) continue;
      endpoints.push({
        method: method.toUpperCase(),
        path,
        desc: op.summary ?? op.description ?? '',
      });
    }
  }
} catch {
  console.warn('[gen-api-list] openapi.json 缺失或解析失败，保留现有生成文件');
  process.exit(0);
}

endpoints.sort((a, b) => a.path.localeCompare(b.path));

const content = `// 本文件由 scripts/gen-api-list.mjs 从 openapi.json 自动生成，请勿手动修改

export interface ApiEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  path: string;
  desc: string;
}

export const API_ENDPOINTS: ApiEndpoint[] = ${JSON.stringify(endpoints, null, 2)};
`;

mkdirSync(outDir, { recursive: true });
writeFileSync(outFile, content);
console.log(`[gen-api-list] 已生成 ${endpoints.length} 个端点 → src/generated/apiEndpoints.ts`);
