-- ============================================================
-- 银杏代取 · 数据库初始化脚本 (Supabase SQL Editor 里整段执行)
-- 订单表 + 行级安全(RLS) + 安全查询函数(RPC)
-- 设计原则：学生手机号+订单号才能查自己的单；管理端凭管理口令操作
--
-- ⚠️ 上线前必改：把下面两处默认口令 ADMIN_CHANGE_ME 换成你自己的
--   （config.js 里的 ADMIN_SECRET 必须与这里一致）
-- ============================================================

-- ---------- 订单表 ----------
create table if not exists public.orders (
  id          bigserial primary key,
  order_no    text unique not null,   -- 订单号 YQ260908xxxx
  status      text not null default 'pending',  -- pending待取件 / picking取件中 / delivering配送中 / done已完成 / cancelled已取消
  station     text not null,          -- 驿站/快递点
  carrier     text default '',        -- 快递公司
  pickup_code text not null,          -- 取件码
  building    text not null,          -- 送哪栋（同心苑A 等）
  room        text default '',        -- 楼层/寝室号
  dropoff     text not null default '楼下',     -- 楼下自取 / 送寝门口
  name        text not null,          -- 下单人称呼
  phone       text not null,          -- 手机号（查单凭证）
  note        text default '',        -- 备注
  fee         numeric not null default 2,       -- 跑腿费（元，线下结算）
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists idx_orders_status on public.orders (status, created_at desc);
create index if not exists idx_orders_no on public.orders (order_no);

-- ---------- 行级安全：默认全拒，只放行“创建” ----------
alter table public.orders enable row level security;

drop policy if exists "anon can insert" on public.orders;
create policy "anon can insert" on public.orders
  for insert to anon
  with check (true);

-- ---------- 函数区（RPC） ----------

-- 学生查单：必须 订单号 + 手机号 都匹配才返回
create or replace function public.query_order(p_no text, p_phone text)
returns setof public.orders
language sql stable security definer set search_path = public as $$
  select * from public.orders
  where order_no = p_no and phone = p_phone;
$$;

-- 管理端校验函数（所有 admin_* 共用）：口令不对直接拒绝
create or replace function public._admin_ok(p_secret text)
returns boolean
language plpgsql stable security definer set search_path = public as $$
begin
  if p_secret is null or p_secret = '' then
    return false;
  end if;
  -- ↓↓↓ 默认口令：上线前改成你自己的，同时改 config.js 的 ADMIN_SECRET ↓↓↓
  if p_secret <> 'ADMIN_CHANGE_ME' then
    return false;
  end if;
  return true;
end;
$$;

-- 管理端：校验管理口令后拉订单列表（可按状态过滤）
create or replace function public.admin_list_orders(p_secret text, p_status text default null, p_limit int default 200)
returns setof public.orders
language sql stable security definer set search_path = public as $$
  select * from public.orders
  where public._admin_ok(p_secret)
    and (p_status is null or status = p_status)
  order by created_at desc
  limit greatest(1, least(p_limit, 500));
$$;

-- 管理端：口令是否正确（登录校验用）
create or replace function public.admin_ping(p_secret text)
returns boolean
language sql stable security definer set search_path = public as $$
  select public._admin_ok(p_secret);
$$;

-- 管理端：统计（今日单量 / 各状态在途单量）
create or replace function public.admin_stats(p_secret text)
returns table(today_count bigint, pending_count bigint, picking_count bigint, delivering_count bigint, done_today bigint)
language sql stable security definer set search_path = public as $$
  select
    (select count(*) from public.orders where created_at::date = current_date)::bigint,
    (select count(*) from public.orders where status = 'pending')::bigint,
    (select count(*) from public.orders where status = 'picking')::bigint,
    (select count(*) from public.orders where status = 'delivering')::bigint,
    (select count(*) from public.orders where status = 'done' and created_at::date = current_date)::bigint
  where public._admin_ok(p_secret);
$$;

-- 管理端：更新状态（口令校验；仅允许合法状态迁移）
create or replace function public.admin_update_status(p_secret text, p_order_no text, p_status text)
returns text
language plpgsql security definer set search_path = public as $$
declare
  cur text;
begin
  if not public._admin_ok(p_secret) then
    return 'FORBIDDEN';
  end if;
  select status into cur from public.orders where order_no = p_order_no;
  if cur is null then
    return 'NOT_FOUND';
  end if;
  if p_status not in ('pending','picking','delivering','done','cancelled') then
    return 'BAD_STATUS';
  end if;
  -- 已完成的单不允许再动（防止误改已完成记录）
  if cur = 'done' and p_status <> 'done' then
    return 'FINISHED';
  end if;
  update public.orders
     set status = p_status, updated_at = now()
   where order_no = p_order_no;
  return 'OK';
end;
$$;
