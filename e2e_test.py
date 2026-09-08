# -*- coding: utf-8 -*-
"""银杏代取 E2E 冒烟测试 v2
学生下单 → 工作台按状态 tab 流转 → 学生查单 → 取消流程
跑法: cdpvenv python e2e_test.py  (需先起 http.server:8765 和 Edge headless:9222)
"""
import json, time, urllib.request, sys
import websocket

BASE = 'http://127.0.0.1:8765'
PHONE = '13800138000'
NAME = '测试君'
PASS_N = 0
FAIL_N = 0

def check(name, cond, extra=''):
    global PASS_N, FAIL_N
    if cond:
        PASS_N += 1
        print('  ✅ PASS:', name, extra)
    else:
        FAIL_N += 1
        print('  ❌ FAIL:', name, extra)

# ---------- CDP ----------
def get_ws():
    for _ in range(30):
        try:
            with urllib.request.urlopen('http://127.0.0.1:9222/json', timeout=3) as r:
                pages = json.loads(r.read())
            for p in pages:
                if p.get('type') == 'page' and p.get('url', '').startswith(('about:blank', 'http://127.0.0.1:8765')):
                    return p['webSocketDebuggerUrl']
        except Exception:
            pass
        time.sleep(0.5)
    raise SystemExit('Edge CDP 未就绪')

ws = websocket.create_connection(get_ws(), timeout=15, suppress_origin=True)
_seq = 0
def cdp(method, params=None):
    global _seq
    _seq += 1
    ws.send(json.dumps({'id': _seq, 'method': method, 'params': params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == _seq:
            if 'error' in msg:
                raise RuntimeError(f"{method}: {msg['error']}")
            return msg.get('result', {})

def ev(expr):
    r = cdp('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
    if r.get('exceptionDetails'):
        raise RuntimeError('JS错误: ' + json.dumps(r['exceptionDetails'], ensure_ascii=False)[:400])
    return r.get('result', {}).get('value')

def nav(url):
    cdp('Page.navigate', {'url': url})
    time.sleep(1.2)

def sleep(s): time.sleep(s)

# ---------- 公共 JS ----------
JS_SUBMIT_ORDER = """(() => {
  const set = (sel, v) => { const el = document.querySelector(sel); el.value = v; el.dispatchEvent(new Event('change')); };
  const inp = (sel, v) => { const el = document.querySelector(sel); el.value = v; el.dispatchEvent(new Event('input')); };
  set('#frmStation', 'STATION'); set('#frmCarrier', '中通'); set('#frmBuilding', 'BLDG');
  inp('#frmCode', 'CODE'); inp('#frmRoom', 'ROOM');
  inp('#frmName', 'NAME'); inp('#frmPhone', 'PHONE'); inp('#frmNote', 'E2E测试单');
  document.getElementById('btnSubmit').click(); return 1;
})()"""
JS_QUERY = """(() => { const q = (sel,v)=>{const e=document.querySelector(sel);e.value=v;e.dispatchEvent(new Event('input'));};
  q('#qryNo','NO'); q('#qryPhone','PHONE'); document.getElementById('btnQuery').click(); return 1; })()"""
JS_BADGE = """(() => (document.querySelector('#resStatus .badge')||{}).textContent || '')()"""
JS_NOW = """(() => (document.querySelector('#resTimeline .tl-step.now .t')||{}).textContent || '')()"""

def student_submit(station, bldg, code, room):
    ev(JS_SUBMIT_ORDER.replace('STATION', station).replace('BLDG', bldg)
       .replace('CODE', code).replace('ROOM', room)
       .replace('NAME', NAME).replace('PHONE', PHONE))
    sleep(2)
    return ev("(document.getElementById('resNo').textContent||'').split(' ')[0]")

def student_query(no):
    ev(JS_QUERY.replace('NO', no).replace('PHONE', PHONE))
    sleep(1.3)

def work_tab(status):
    ev("""(() => { const t = [...document.querySelectorAll('.ztab')].find(x => x.dataset.s === 'STATUS');
      if (t) t.click(); return !!t; })()""".replace('STATUS', status))
    sleep(1.4)

def work_find(no):
    return ev("""(() => {
      const card = [...document.querySelectorAll('.order-card')].find(c => c.dataset.no === 'NO');
      return card ? (card.querySelector('.badge')||{}).textContent : 'GONE';
    })()""".replace('NO', no))

def work_click(no, act):
    return ev("""(() => {
      const card = [...document.querySelectorAll('.order-card')].find(c => c.dataset.no === 'NO');
      if (!card) return 'CARD_MISSING';
      const btn = card.querySelector('button[data-act="ACT"]');
      if (!btn) return 'BTN_MISSING';
      btn.click(); return 'CLICKED';
    })()""".replace('NO', no).replace('ACT', act))

# ---------- 测试开始 ----------
print('== T0 清理演示数据 ==')
nav(BASE + '/index.html'); sleep(0.8)
ev("localStorage.clear(); location.reload(); 1")
sleep(1.4)
print('   已清空')

print('== T1 学生端下单 ==')
no1 = student_submit('菜鸟驿站', '同心苑A', '1-3-0527', '3-512')
check('下单成功生成 YQ 订单号', str(no1).startswith('YQ'), no1)
student_query(no1)
check('下单后自动展示订单：待取件/订单已提交', ev(JS_BADGE) == '待取件' and ev(JS_NOW) == '订单已提交')
check('费用与楼栋信息正确', '¥2' in ev("document.getElementById('resFee').textContent")
      and '同心苑A' in ev("document.getElementById('resInfo').textContent"))

print('== T2 工作台：待取件视图有单 + 驿站分组 ==')
nav(BASE + '/admin.html'); sleep(1.6)
r2 = ev("""(() => ({
  work: document.getElementById('workView').style.display !== 'none',
  groups: [...document.querySelectorAll('.station-head')].map(g => g.textContent.replace(/\\s+/g,' '))
}))()""")
check('演示模式自动进入工作台', r2['work'])
check('待取件按驿站分组（菜鸟驿站组含新单）', any('菜鸟驿站' in g for g in r2['groups']))

print('== T3 完整流转：待取件→取件中→配送中→已完成（跨 tab 验证）==')
b_pending = work_find(no1)
check('待取件 tab 里有新单', b_pending == '待取件', f'-> {b_pending}')
work_click(no1, 'next'); sleep(1.2)
check('点[已取到，去配送]后从待取件列表消失', work_find(no1) == 'GONE')
work_tab('picking')
check('取件中 tab：徽章=取件中', work_find(no1) == '取件中')
work_click(no1, 'next'); sleep(1.2)
work_tab('delivering')
check('配送中 tab：徽章=配送中', work_find(no1) == '配送中')
work_click(no1, 'next'); sleep(1.2)
work_tab('done')
check('已完成 tab：徽章=已完成', work_find(no1) == '已完成')

print('== T4 学生端回查已完成订单 ==')
nav(BASE + '/index.html'); sleep(0.8)
student_query(no1)
done_steps = ev("document.querySelectorAll('#resTimeline .tl-step.done').length")
check('状态=已完成 + 前3步绿 + 当前步=已送达',
      ev(JS_BADGE) == '已完成' and done_steps == 3 and ev(JS_NOW) == '已送达',
      f'doneSteps={done_steps}')

print('== T5 取消流程 ==')
no2 = student_submit('妈妈驿站', '修心苑B', 'A-26-108', '2-101')
check('第二单创建成功', str(no2).startswith('YQ') and no2 != no1, no2)
nav(BASE + '/admin.html'); sleep(1.6)
ev("window.confirm = () => true; 1")
work_tab('pending')
r5 = work_click(no2, 'cancel'); sleep(1.2)
check('工作台点取消', r5 == 'CLICKED')
work_tab('cancelled')
check('取消 tab：徽章=已取消', work_find(no2) == '已取消')
nav(BASE + '/index.html'); sleep(0.8)
student_query(no2)
check('学生端显示 已取消 + 时间线=订单已取消',
      ev(JS_BADGE) == '已取消' and ev(JS_NOW) == '订单已取消')

print('== T6 错误口令拦截（工作台） ==')
nav(BASE + '/admin.html'); sleep(1.0)
# 演示模式口令校验（模拟真模式逻辑）：先退出登录界面再验
ev("""(() => {
  const lv = document.getElementById('loginView'); lv.style.display='flex';
  document.getElementById('workView').style.display='none'; return 1;
})()""")
ev("document.getElementById('loginSecret').value = 'wrong-password'; 1")
ev("document.getElementById('btnLogin').click(); 1")
sleep(1.2)
login_toast = ev("document.getElementById('toast').textContent")
work_still = ev("document.getElementById('workView').style.display")
check('错误口令被拦截（提示口令不对，工作台不进入）',
      '口令不对' in login_toast and work_still == 'none',
      f'toast="{login_toast}"')

print()
print(f'======== 结果: {PASS_N} 通过 / {FAIL_N} 失败 ========')
sys.exit(1 if FAIL_N else 0)
