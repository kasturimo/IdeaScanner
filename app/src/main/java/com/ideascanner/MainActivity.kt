package com.ideascanner

import android.os.Bundle
import android.util.Log
import android.widget.Button
import androidx.appcompat.app.AppCompatActivity
import com.android.billingclient.api.*
import okhttp3.*
import org.json.JSONObject
import java.io.IOException

class MainActivity : AppCompatActivity(), PurchasesUpdatedListener {

    private lateinit var billingClient: BillingClient
    private val backendUrl = "https://your-backend.onrender.com/verify_purchase" // 🔹 replace with your Render URL

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val buyButton: Button = findViewById(R.id.buyButton)

        // Setup Google Billing
        billingClient = BillingClient.newBuilder(this)
            .enablePendingPurchases()
            .setListener(this)
            .build()

        billingClient.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(billingResult: BillingResult) {
                if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                    Log.d("Billing", "Billing Client Ready")
                }
            }

            override fun onBillingServiceDisconnected() {
                Log.e("Billing", "Billing Service Disconnected")
            }
        })

        buyButton.setOnClickListener {
            val skuList = listOf("idea_analysis") // 🔹 must match Play Console product ID
            val params = SkuDetailsParams.newBuilder()
            params.setSkusList(skuList).setType(BillingClient.SkuType.INAPP)

            billingClient.querySkuDetailsAsync(params.build()) { billingResult, skuDetailsList ->
                if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && !skuDetailsList.isNullOrEmpty()) {
                    val flowParams = BillingFlowParams.newBuilder()
                        .setSkuDetails(skuDetailsList[0])
                        .build()
                    billingClient.launchBillingFlow(this, flowParams)
                }
            }
        }
    }

    override fun onPurchasesUpdated(billingResult: BillingResult, purchases: MutableList<Purchase>?) {
        if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
            for (purchase in purchases) {
                verifyPurchaseWithBackend(purchase)
            }
        } else if (billingResult.responseCode == BillingClient.BillingResponseCode.USER_CANCELED) {
            Log.d("Billing", "User canceled purchase")
        } else {
            Log.e("Billing", "Purchase failed: ${billingResult.debugMessage}")
        }
    }

    private fun verifyPurchaseWithBackend(purchase: Purchase) {
        val client = OkHttpClient()
        val requestBody = JSONObject()
        requestBody.put("purchase_token", purchase.purchaseToken)
        requestBody.put("product_id", purchase.products[0])

        val body = RequestBody.create(
            MediaType.parse("application/json; charset=utf-8"),
            requestBody.toString()
        )

        val request = Request.Builder()
            .url(backendUrl)
            .post(body)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e("Backend", "Failed to verify purchase: ${e.message}")
            }

            override fun onResponse(call: Call, response: Response) {
                val responseBody = response.body()?.string()
                Log.d("Backend", "Verification response: $responseBody")
            }
        })
    }
}



