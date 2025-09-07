package com.ideascanner

import retrofit2.Call
import retrofit2.http.*

data class RegisterRequest(val email:String, val password:String, val location:String?)
data class AuthResponse(val ok:Boolean, val access_token:String?, val user: Map<String,Any>?)
data class LoginRequest(val email:String, val password:String)
data class AnalyzeRequest(val idea:String, val location:String?)
data class AnalyzeResponse(val ok:Boolean, val analysis:String?, val score:Int?)
data class AddCreditsRequest(val packageName:String, val productId:String, val purchaseToken:String, val creditsAmount:Int)

interface ApiService {
    @POST("/api/register")
    fun register(@Body req: RegisterRequest): Call<AuthResponse>

    @POST("/api/login")
    fun login(@Body req: LoginRequest): Call<AuthResponse>

    @POST("/api/google_login")
    fun googleLogin(@Body body: Map<String, String>): Call<AuthResponse>

    @POST("/api/analyze")
    fun analyze(@Header("Authorization") bearer: String, @Body req: AnalyzeRequest): Call<AnalyzeResponse>

    @GET("/api/history")
    fun history(@Header("Authorization") bearer: String): Call<Map<String, Any>>

    @POST("/api/add_credits")
    fun addCredits(@Header("Authorization") bearer: String, @Body req: AddCreditsRequest): Call<Map<String, Any>>
}
