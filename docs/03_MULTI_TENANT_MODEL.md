# Modelo Multi-Tenant

## Estratégia

Banco único com tenant_id.

## Estrutura

```
tenants
users
user_tenants
roles
permissions
```

## Regras

* todo dado tem tenant_id
* backend resolve tenant
* usuário pode ter múltiplos tenants

## Papéis

* saas_admin
* tenant_admin
* manager
* financial
* commercial
* operations

## Configurações por tenant

* nome da clínica
* logo
* cores
* timezone
* moeda
* integrações
* limites de IA

## Integrações

* clinicorp
* contaazul

## IA

* limite por tenant
* consumo mensal
* logs de uso

## Segurança

* isolamento obrigatório
* sem acesso cruzado
