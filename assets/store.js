/* ============================================================
 * 银杏代取 · 数据层
 * 一套接口，两种实现：
 *   DEMO_MODE=true  → localStorage 本地模拟（演示/自测用）
 *   DEMO_MODE=false → Supabase 真线上库（多人共享）
 * 页面上统一调 window.API.xxx()，不用关心底下是哪套。
 * ============================================================ */

(function () {
  const LS_KEY = 'yinhe_qudai_orders_v1';

  // ---------- 工具 ----------
  function pad(n, w) { return String(n).padStart(w, '0'); }
  function genOrderNo() {
    const d = new Date();
    const ymd = String(d.getFullYear()).slice(2) + pad(d.getMonth() + 1, 2) + pad(d.getDate(), 2);
    const rand = pad(Math.floor(Math.random() * 10000), 4);
    return 'YQ' + ymd + rand;   // 例：YQ2609080342
  }
  function nowISO() { return new Date().toISOString(); }

  // ---------- 演示模式：localStorage ----------
  function seedDemoOrders() {
    const mk = (no, status, station, code, building, room, dropoff, name, phone, note, fee, minsAgo) => ({
      order_no: no, status, station, carrier: '中通', pickup_code: code,
      building, room, dropoff, name, phone, note, fee,
      created_at: new Date(Date.now() - minsAgo * 60000).toISOString(),
      updated_at: new Date(Date.now() - minsAgo * 60000).toISOString()
    });
    return [
      mk('YQ2609080342', 'pending',    '菜鸟驿站',   '1-3-0527', '诚心苑B', '3-512', '楼下',   '小林', '13800001111', '', 2, 8),
      mk('YQ2609080331', 'pending',    '妈妈驿站',   'A-26-108', '同心苑A', '5-201', '送寝门口', '阿杰', '13900002222', '大件行李箱，麻烦帮忙抬一下', 3, 25),
      mk('YQ2609080319', 'picking',    '菜鸟驿站',   '1-3-0419', '清心苑C', '2-301', '楼下',   '小张', '13700003333', '', 2, 55),
      mk('YQ2609080298', 'delivering', '丰巢快递柜', '柜3-214',  '修心苑B', '4-102', '送寝门口', '雨桐', '13600004444', '先打电话，可能在图书馆', 3, 120),
      mk('YQ2609080276', 'done',       '菜鸟驿站',   '1-2-0388', '同心苑C', '1-105', '楼下',   '阿泽', '13500005555', '', 2, 200)
    ];
  }

  function lsAll() {
    try {
      const arr = JSON.parse(localStorage.getItem(LS_KEY) || '[]');
      if (localStorage.getItem('yinhe_qudai_seeded_v1') !== '1') {
        // 首次进入放几条演示数据，好展示效果（只种一次）
        const seed = seedDemoOrders();
        localStorage.setItem(LS_KEY, JSON.stringify(seed));
        localStorage.setItem('yinhe_qudai_seeded_v1', '1');
        return seed;
      }
      return arr;
    } catch (e) { return seedDemoOrders(); }
  }
  function lsSave(arr) { localStorage.setItem(LS_KEY, JSON.stringify(arr)); }

  // ---------- 状态文案 ----------
  const STATUS_TEXT = {
    pending: '待取件', picking: '取件中', delivering: '配送中',
    done: '已完成', cancelled: '已取消'
  };
  const STATUS_NEXT = {               // 管理端按钮流转
    pending: 'picking', picking: 'delivering', delivering: 'done'
  };
  const NEXT_LABEL = {
    pending: '已取到，去配送', picking: '开始配送', delivering: '送达完成'
  };

  // ---------- Supabase 实例 ----------
  let sb = null;
  function sbClient() {
    if (sb) return sb;
    if (typeof supabase === 'undefined') throw new Error('supabase 库未加载');
    sb = supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_ANON);
    return sb;
  }
  function errMsg(e, fallback) {
    return (e && e.message) ? e.message : fallback;
  }

  // ---------- 统一对外接口 ----------
  window.API = {
    STATUS_TEXT, STATUS_NEXT, NEXT_LABEL,
    isDemo: () => CFG.DEMO_MODE,
    genOrderNo,

    // 学生：下单
    async createOrder(f) {
      const order = {
        order_no: genOrderNo(),
        status: 'pending',
        station: f.station, carrier: f.carrier || '', pickup_code: f.pickup_code,
        building: f.building, room: f.room || '', dropoff: f.dropoff,
        name: f.name, phone: f.phone, note: f.note || '',
        fee: Number(f.fee), created_at: nowISO(), updated_at: nowISO()
      };
      if (CFG.DEMO_MODE) {
        const arr = lsAll();
        arr.unshift(order);
        lsSave(arr);
        return { ok: true, order_no: order.order_no };
      }
      const { error } = await sbClient().from('orders').insert(order);
      if (error) return { ok: false, msg: errMsg(error, '下单失败，请重试') };
      return { ok: true, order_no: order.order_no };
    },

    // 学生：凭订单号+手机号查单
    async queryOrder(no, phone) {
      if (CFG.DEMO_MODE) {
        const hit = lsAll().find(o => o.order_no === no && o.phone === phone);
        return hit || null;
      }
      const { data, error } = await sbClient()
        .rpc('query_order', { p_no: no, p_phone: phone });
      if (error) throw error;
      return (data && data.length) ? data[0] : null;
    },

    // 管理端：校验口令（demo 直接过）
    async checkSecret(secret) {
      if (CFG.DEMO_MODE) return secret === CFG.ADMIN_SECRET;
      // 真模式下以数据库校验为准
      const { data, error } = await sbClient()
        .rpc('admin_ping', { p_secret: secret });
      if (error) throw error;
      return data === true;
    },

    // 管理端：拉单（可按状态过滤，null=全部）
    async listOrders(status) {
      if (CFG.DEMO_MODE) {
        const all = lsAll();
        const list = status ? all.filter(o => o.status === status) : all;
        return [...list].sort((a, b) => b.created_at.localeCompare(a.created_at));
      }
      const { data, error } = await sbClient()
        .rpc('admin_list_orders', {
          p_secret: API._secret, p_status: status || null, p_limit: 300
        });
      if (error) throw error;
      return data || [];
    },

    // 管理端：统计
    async stats() {
      if (CFG.DEMO_MODE) {
        const all = lsAll();
        const today = all.filter(o => o.created_at.slice(0, 10) === nowISO().slice(0, 10));
        return {
          today_count: today.length,
          pending_count: all.filter(o => o.status === 'pending').length,
          picking_count: all.filter(o => o.status === 'picking').length,
          delivering_count: all.filter(o => o.status === 'delivering').length,
          done_today: today.filter(o => o.status === 'done').length
        };
      }
      const { data, error } = await sbClient()
        .rpc('admin_stats', { p_secret: API._secret });
      if (error) throw error;
      return data || {};
    },

    // 管理端：状态流转
    async updateStatus(no, status) {
      if (CFG.DEMO_MODE) {
        const arr = lsAll();
        const o = arr.find(x => x.order_no === no);
        if (!o) return { ok: false, msg: '订单不存在' };
        if (o.status === 'done' && status !== 'done') return { ok: false, msg: '已完成订单不可改动' };
        o.status = status; o.updated_at = nowISO();
        lsSave(arr);
        return { ok: true };
      }
      const { data, error } = await sbClient()
        .rpc('admin_update_status', { p_secret: API._secret, p_order_no: no, p_status: status });
      if (error) return { ok: false, msg: errMsg(error, '操作失败') };
      if (data === 'FORBIDDEN') return { ok: false, msg: '管理口令不对，请重新登录' };
      if (data === 'NOT_FOUND') return { ok: false, msg: '订单不存在' };
      if (data === 'FINISHED') return { ok: false, msg: '已完成订单不可改动' };
      if (data !== 'OK') return { ok: false, msg: '操作失败(' + data + ')' };
      return { ok: true };
    }
  };

  API._secret = '';   // 管理端登录后暂存口令（仅本次会话内存中）
})();
