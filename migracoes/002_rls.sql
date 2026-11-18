-- Ninguém de fora lê ou escreve pela API pública. O robô usa a conexão direta
-- (que ignora RLS); o site (plano 2) vai definir o acesso de leitura.
alter table stores   enable row level security;
alter table models   enable row level security;
alter table runs     enable row level security;
alter table listings enable row level security;
alter table prices   enable row level security;
