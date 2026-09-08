# 🛵 银杏代取 —— 校园快递代取平台（MVP）

> 像美团跑腿一样下单，快递驿站到寝室的最后 100 米。
> 学生端下单 → 跑腿团队工作台接单 → 取件码取件 → 送到楼下/寝室 → 当面付款。

## 三件套

| 文件 | 干什么 | 谁用 |
|---|---|---|
| `index.html` | 学生端：下单 / 查进度 / 我的记录 | 全校同学 |
| `admin.html` | 跑腿工作台：接单、驿站分组、状态流转、统计 | 老板和跑腿团队 |
| `schema.sql` | 数据库初始化脚本 | 老板注册 Supabase 后执行一次 |

所有业务配置（驿站、价格、楼栋、站点名、口令）都在 **`config.js`** 一个文件里，改完刷新即生效。

---

## 🎮 先看效果（演示模式，30 秒）

默认 `config.js` 里 `DEMO_MODE: true` —— 不依赖任何后端，订单存在浏览器本地，适合自己先点一遍：

```bash
cd 项目目录
python -m http.server 8765
# 手机/浏览器打开 http://127.0.0.1:8765/index.html  学生端
#              http://127.0.0.1:8765/admin.html     工作台（演示模式自动登录）
```

流程：学生端下个单 → 工作台看到新单（按驿站分组）→ 点「已取到，去配送」→「开始配送」→「送达完成」→ 回学生端查单，时间线全绿。

> ⚠️ 演示模式数据只存在**当前浏览器**，换手机就看不到。要真多人用，走下面 10 分钟启用。

---

## 🚀 正式启用（10 分钟，0 元成本）

### 第 1 步：注册 Supabase（免费后端）

1. 浏览器打开 **https://supabase.com** → 右上 `Start your project`
2. 用 GitHub 或邮箱注册登录
3. 登录后点 `New project`：
   - Name 随便填（如 `yinhe-qudai`）
   - Database Password：**记下来**（以后用）
   - Region 选 **Southeast Asia (Singapore)**（离国内近些）
4. 等 1~2 分钟项目创建完成

### 第 2 步：建表 + 安全函数（一次搞定）

1. 左侧菜单点 **SQL Editor** → 点 **New query**
2. 把项目里 `schema.sql` 的**全部内容**粘贴进去
3. **执行前**：把文里两处 `ADMIN_CHANGE_ME` 换成你自己的管理口令（比如 `wojiaodaiqv2026`）
4. 点底部 **Run**（绿色按钮），看到 `Success. No rows returned` 即成功

### 第 3 步：拿 API 钥匙填进 config.js

1. 左侧 **Project Settings → API**
2. 复制两项：
   - `Project URL`（长这样：`https://xxxx.supabase.co`）→ 填 `config.js` 的 `SUPABASE_URL`
   - `anon public` 那一串（`eyJ...`）→ 填 `config.js` 的 `SUPABASE_ANON`
3. `config.js` 里改三处：
   ```js
   DEMO_MODE: false,
   SUPABASE_URL:  'https://xxxx.supabase.co',
   SUPABASE_ANON: 'eyJ...',
   ADMIN_SECRET: '和 schema.sql 里改的一模一样',
   ```

### 第 4 步：上线给同学用

项目是 GitHub Pages 部署，访问和 yinhe-campus 同款链路：

- 主站（海外直连）：`https://ntex1331.github.io/yinhe-qudai/`
- 国内加速（推荐发这个）：`https://cdn.jsdelivr.net/gh/nTex1331/yinhe-qudai@main/index.html`

**发给同学就发国内加速那一条**，手机浏览器直接打开，可"添加到主屏幕"当 App 用。

---

## 🛠 日常管理

### 改驿站 / 快递公司 / 楼栋 / 价格
全在 `config.js` 顶部，照格式增删即可。比如驿站改名、加新快递柜：

```js
STATIONS: ['菜鸟驿站', '妈妈驿站', ..., '9号楼新驿站'],
FEE_DROP_LOBBY: 2,   // 楼下 ¥2
FEE_DROP_DOOR: 3,    // 送寝门口 ¥3
```

### 改平台名
`config.js` → `APP_NAME`，如改成「银杏闪取」，两个页面标题一起变。

### 换管理口令
改**两处**且保持一致：`schema.sql` 里的常量（要重新 Run 一次 SQL）+ `config.js` 的 `ADMIN_SECRET`。

### 数据/订单去哪看？
Supabase 控制台 → **Table Editor** → `orders` 表，每一单都在这，可导出 CSV 做账。

---

## 🔒 安全设计（为什么这样设计）

| 问题 | 方案 |
|---|---|
| 取件码=快递身份证，不能全校可见 | 订单表默认**禁止任何人直接读**（RLS）；学生必须「订单号+本人手机号」双匹配才能查到自己那单（RPC） |
| 工作台不能谁都能进 | 管理口令在**数据库函数里二次校验**，前端页面口令只是第一道门 |
| 学生乱改别人订单 | 表只放行「创建」；改状态只能走管理端 RPC |
| 平台经手钱？ | MVP 不碰钱，**线下当面付**，跑腿费页面明示。v2 可接微信支付商户 |

---

## 🧪 自动化测试

```bash
# 起本地服务 + Edge/Chrome headless 调试端口后：
python e2e_test.py
# 覆盖：下单→查单→工作台全状态流转→取消→口令拦截（演示模式）
```

---

## 🗺 v2 路线图（跑通后再说）

- [ ] 跑腿员多账号系统（谁接的单一目了然）
- [ ] 微信公众号/小程序入口
- [ ] 在线支付（微信支付商户号）
- [ ] 大件/加急加价规则、满减券拉新
- [ ] 每日营收报表导出

---

*Made by 老黑 for 老板 · MVP v1.0 · 2026-09*
