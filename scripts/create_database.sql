-- ============================================
-- AgroTalhões - Script de Criação do Banco
-- SQL Server Express
-- ============================================

-- Verificar se o banco já existe e criar
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'db_talhoes')
BEGIN
    CREATE DATABASE db_talhoes;
    PRINT 'Banco de dados db_talhoes criado com sucesso!';
END
ELSE
BEGIN
    PRINT 'Banco de dados db_talhoes já existe.';
END
GO

-- Usar o banco criado
USE db_talhoes;
GO

PRINT 'Banco de dados configurado. Execute as migrações do Django para criar as tabelas.';
GO
