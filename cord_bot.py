[1mdiff --git a/discord_bot.py b/discord_bot.py[m
[1mindex 45dd4a5..0e9feef 100644[m
[1m--- a/discord_bot.py[m
[1m+++ b/discord_bot.py[m
[36m@@ -934,6 +934,146 @@[m [masync def test_api_command(ctx):[m
         logger.error(f"Erreur dans la commande test-api: {e}")[m
         await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")[m
 [m
[32m+[m[32m@bot.command(name='test-webhook-endpoints')[m
[32m+[m[32masync def test_webhook_endpoints_command(ctx):[m
[32m+[m[32m    """Commande pour tester différents endpoints webhook v2"""[m
[32m+[m[32m    try:[m
[32m+[m[32m        if not ctx.guild:[m
[32m+[m[32m            await ctx.reply("❌ Cette commande ne peut être utilisée que dans un serveur.")[m
[32m+[m[32m            return[m
[32m+[m[41m        [m
[32m+[m[32m        embed = discord.Embed([m
[32m+[m[32m            title="🧪 Test Endpoints Webhook v2",[m
[32m+[m[32m            description="Test des différents endpoints webhook v2...",[m
[32m+[m[32m            color=0x00BFFF[m
[32m+[m[32m        )[m
[32m+[m[32m        embed.set_footer(text="Farcaster Tracker Bot")[m
[32m+[m[41m        [m
[32m+[m[32m        message = await ctx.reply(embed=embed)[m
[32m+[m[41m        [m
[32m+[m[32m        webhook_id = config.NEYNAR_WEBHOOK_ID[m
[32m+[m[32m        client = get_neynar_client()[m
[32m+[m[41m        [m
[32m+[m[32m        if client is None:[m
[32m+[m[32m            await ctx.reply("❌ Client Neynar non initialisé")[m
[32m+[m[32m            return[m
[32m+[m[41m        [m
[32m+[m[32m        # Test 1: Endpoint actuel[m
[32m+[m[32m        try:[m
[32m+[m[32m            import requests[m
[32m+[m[32m            headers = client.headers[m
[32m+[m[41m            [m
[32m+[m[32m            # Test 1a: /v2/farcaster/webhook/{id}[m
[32m+[m[32m            response = requests.get([m
[32m+[m[32m                f"https://api.neynar.com/v2/farcaster/webhook/{webhook_id}",[m
[32m+[m[32m                headers=headers,[m
[32m+[m[32m                timeout=10[m
[32m+[m[32m            )[m
[32m+[m[32m            embed.add_field([m
[32m+[m[32m                name="1️⃣ /v2/farcaster/webhook/{id}",[m
[32m+[m[32m                value=f"Status: {response.status_code}\nResponse: {response.text[:100]}...",[m
[32m+[m[32m                inline=False[m
[32m+[m[32m            )[m
[32m+[m[32m        except Exception as e:[m
[32m+[m[32m            embed.add_field([m
[32m+[m[32m                name="1️⃣ /v2/farcaster/webhook/{id}",[m
[32m+[m[32m                value=f"Erreur: {str(e)}",[m
[32m+[m[32m                inline=False[m
[32m+[m[32m            )[m
[32m+[m[41m        [m
[32m+[m[32m        await message.edit(embed=embed)[m
[32m+[m[41m        [m
[32m+[m[32m        # Test 2: Endpoint alternatif[m
[32m+[m[32m        try:[m
[32m+[m[32m            # Test 2a: /v2/farcaster/webhooks/{id}[m
[32m+[m[32m            response = requests.get([m
[32m+[m[32m                f"https://api.neynar.com/v2/farcaster/webhooks/{webhook_id}",[m
[32m+[m[32m                headers=headers,[m
[32m+[m[32m                timeout=10[m
[32m+[m[32m            )[m
[32m+[m[32m            embed.add_field([m
[32m+[m[32m                name="2️⃣ /v2/farcaster/webhooks/{id}",[m
[32m+[m[32m                value=f"Status: {response.status_code}\nResponse: {response.text[:100]}...",[m
[32m+[m[32m                inline=False[m
[32m+[m[32m            )[m
[32m+[m[32m        except Exception as e:[m
[32m+[m[32m            embed.add_field([m
[32m+[m[32m                name="2️⃣ /v2/farcaster/webhooks/{id}",[m
[32m+[m[32m                value=f"Erreur: {str(e)}",[m
[32m+[m[32m                inline=False[m
[32m+[m[32m            )[m
[32m+[m[41m        [m
[32m+[m[32m        await message.edit(embed=embed)[m
[32m+[m[41m        [m
[32m+[m[32m        # Test 3: Endpoint avec query params[m
[32m+[m[32m        try:[m
[32m+[m[32m            # Test 3a: /v2/farcaster/webhook?id={id}[m
[32m+[m[32m            response = requests.get([m
[32m+[m[32m                f"https://api.neynar.com/v2/farcaster/webhook?id={webhook_id}",[m
[32m+[m[32m                headers=headers,[m
[32m+[m[32m                timeout=10[m
[32m+[m[32m            )[m
[32m+[m[32m            embed.add_field([m
[32m+[m[32m                name="3️⃣ /v2/farcaster/webhook?id={id}",[m
[32m+[m[32m                value=f"Status: {response.status_code}\nResponse: {response.text[:100]}...",[m
[32m+[m[32m                inline=False[m
[32m+[m[32m            )[m
[32m+[m[32m        except Exception as e:[m
[32m+[m[32m            embed.add_field([m
[32m+[m[32m                name="3️⃣ /v2/farcaster/webhook?id={id}",[m
[32m+[m[32m                value=f"Erreur: {str(e)}",[m
[32m+[m[32m                inline=False[m
[32m+[m[32m            )[m
[32m+[m[41m        [m
[32m+[m[32m        await message.edit(embed=embed)[m
[32m+[m[41m        [m
[32m+[m[32m        # Test 4: Lister tous les webhooks[m
[32m+[m[32m        try:[m
[32m+[m[32m            # Test 4a: /v2/farcaster/webhooks (liste)[m
[32m+[m[32m            response = requests.get([m
[32m+[m[32m                "https://api.neynar.com/v2/farcaster/webhooks",[m
[32m+[m[32m                headers=headers,[m
[32m+[m[32m                timeout=10[m
[32m+[m[32m            )[m
[32m+[m[32m            if response.status_code == 200:[m
[32m+[m[32m                webhooks = response.json()[m
[32m+[m[32m                webhook_list = [][m
[32m+[m[32m                if isinstance(webhooks, list):[m
[32m+[m[32m                    for wh in webhooks[:3]:  # Limiter à 3 pour l'affichage[m
[32m+[m[32m                        webhook_list.append(f"ID: {wh.get('id', 'N/A')}, Active: {wh.get('active', 'N/A')}")[m
[32m+[m[32m                elif isinstance(webhooks, dict) and 'webhooks' in webhooks:[m
[32m+[m[32m                    for wh in webhooks['webhooks'][:3]:[m
[32m+[m[32m                        webhook_list.append(f"ID: {wh.get('id', 'N/A')}, Active: {wh.get('active', 'N/A')}")[m
[32m+[m[41m                [m
[32m+[m[32m                embed.add_field([m
[32m+[m[32m                    name="4️⃣ /v2/farcaster/webhooks (liste)",[m
[32m+[m[32m                    value=f"Status: {response.status_code}\nWebhooks: {', '.join(webhook_list) if webhook_list else 'Aucun'}",[m
[32m+[m[32m                    inline=False[m
[32m+[m[32m                )[m
[32m+[m[32m            else:[m
[32m+[m[32m                embed.add_field([m
[32m+[m[32m                    name="4️⃣ /v2/farcaster/webhooks (liste)",[m
[32m+[m[32m                    value=f"Status: {response.status_code}\nResponse: {response.text[:100]}...",[m
[32m+[m[32m                    inline=False[m
[32m+[m[32m                )[m
[32m+[m[32m        except Exception as e:[m
[32m+[m[32m            embed.add_field([m
[32m+[m[32m                name="4️⃣ /v2/farcaster/webhooks (liste)",[m
[32m+[m[32m                value=f"Erreur: {str(e)}",[m
[32m+[m[32m                inline=False[m
[32m+[m[32m            )[m
[32m+[m[41m        [m
[32m+[m[32m        # Mise à jour finale[m
[32m+[m[32m        embed.description = "Test des endpoints webhook terminé"[m
[32m+[m[32m        embed.color = 0x00FF00 if any("200" in field.value for field in embed.fields) else 0xFF0000[m
[32m+[m[32m        await message.edit(embed=embed)[m
[32m+[m[41m        [m
[32m+[m[32m        logger.info(f"Test endpoints webhook effectué dans {ctx.guild.name} par {ctx.author.name}")[m
[32m+[m[41m        [m
[32m+[m[32m    except Exception as e:[m
[32m+[m[32m        logger.error(f"Erreur dans la commande test-webhook-endpoints: {e}")[m
[32m+[m[32m        await ctx.reply(f"❌ Une erreur est survenue: {str(e)}")[m
[32m+[m
 @bot.command(name='far-help')[m
 async def far_help(ctx):[m
     """Afficher l'aide pour les commandes Farcaster"""[m
