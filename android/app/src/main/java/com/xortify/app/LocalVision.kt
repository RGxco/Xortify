package com.xortify.app

import android.content.ContentResolver
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BitmapRegionDecoder
import android.graphics.Matrix
import android.graphics.Rect
import android.net.Uri
import android.content.res.AssetManager
import androidx.exifinterface.media.ExifInterface
import ai.onnxruntime.OnnxJavaType
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.Locale

const val MODEL_SHA256 = "bd61897fc7744478bd42bb7714ed22769cc0bf05a0980c9ce03dcf48cace26bc"
const val MODEL_BYTES = 5_148_096L
private const val MODEL_URL = "https://huggingface.co/ketiswp/mediapipe-EfficientNet-Lite0-ImageNet-224-int8-uint8-onnx/resolve/main/model.onnx"
private const val MODEL_NAME = "efficientnet_lite0_imagenet_int8.onnx"

fun modelFile(directory: File): File = File(directory, "models/$MODEL_NAME")

fun isModelInstalled(directory: File): Boolean {
    val file = modelFile(directory)
    return file.isFile && file.length() == MODEL_BYTES && file.sha256() == MODEL_SHA256
}

fun installLocalModel(directory: File, progress: (Long) -> Unit): File {
    val target = modelFile(directory)
    if (isModelInstalled(directory)) return target
    target.parentFile?.mkdirs()
    val partial = File(target.parentFile, "$MODEL_NAME.part")
    val connection = URL(MODEL_URL).openConnection() as HttpURLConnection
    connection.connectTimeout = 20_000
    connection.readTimeout = 30_000
    connection.setRequestProperty("User-Agent", "Xortify-Android/0.1 local-model-installer")
    try {
        connection.inputStream.use { input ->
            partial.outputStream().buffered().use { output ->
                val buffer = ByteArray(128 * 1024)
                var done = 0L
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    output.write(buffer, 0, count)
                    done += count
                    progress(done)
                }
            }
        }
        if (partial.length() != MODEL_BYTES || partial.sha256() != MODEL_SHA256) {
            throw IllegalStateException("The downloaded image model failed its integrity check.")
        }
        if (target.exists() && !target.delete()) throw IllegalStateException("Could not replace the invalid image model file.")
        if (!partial.renameTo(target)) throw IllegalStateException("Could not save the image model on this device.")
        return target
    } catch (error: Exception) {
        partial.delete()
        throw error
    } finally {
        connection.disconnect()
    }
}

private fun File.sha256(): String {
    val digest = MessageDigest.getInstance("SHA-256")
    inputStream().buffered().use { input ->
        val block = ByteArray(128 * 1024)
        while (true) {
            val count = input.read(block)
            if (count < 0) break
            digest.update(block, 0, count)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}

data class VisualGuess(val label: String, val topic: String?, val confidence: Float)

class LocalVision(directory: File, private val resolver: ContentResolver, assets: AssetManager, private val cacheDirectory: File) : AutoCloseable {
    private val environment = OrtEnvironment.getEnvironment()
    private val session: OrtSession = environment.createSession(modelFile(directory).absolutePath, OrtSession.SessionOptions())
    private val inputName = session.inputNames.first()
    private val labels: List<String> = assets.open("imagenet_labels.txt").bufferedReader().useLines { lines ->
        val all = lines.filter { it.isNotBlank() }.toList()
        if (all.firstOrNull()?.equals("background", true) == true) all.drop(1) else all
    }

    fun predict(uri: Uri): VisualGuess? {
        if (labels.size != 1000) return null
        val imageFile = File.createTempFile("xortify-image-", ".tmp", cacheDirectory)
        try {
            var tooLarge = false
            val imageStream = resolver.openInputStream(uri) ?: run { imageFile.delete(); return null }
            imageStream.use { input ->
                imageFile.outputStream().buffered().use { output ->
                    val chunk = ByteArray(64 * 1024)
                    var total = 0L
                    while (true) {
                        val count = input.read(chunk)
                        if (count < 0) break
                        total += count
                        if (total > 64L * 1024 * 1024) { tooLarge = true; break }
                        output.write(chunk, 0, count)
                    }
                }
            } ?: return null
            if (tooLarge) { imageFile.delete(); return null }
        } catch (_: Exception) {
            imageFile.delete()
            return null
        }
        try {
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(imageFile.absolutePath, options)
        if (options.outWidth <= 0 || options.outHeight <= 0) return null
        val side = minOf(options.outWidth, options.outHeight)
        val left = (options.outWidth - side) / 2
        val top = (options.outHeight - side) / 2
        val sample = (side / 224).coerceAtLeast(1)
        val crop = try {
            val decoder = BitmapRegionDecoder.newInstance(imageFile.absolutePath, false)
            try {
                decoder.decodeRegion(Rect(left, top, left + side, top + side), BitmapFactory.Options().apply {
                    inSampleSize = sample
                    inPreferredConfig = Bitmap.Config.ARGB_8888
                })
            } finally { decoder.recycle() }
        } catch (_: Exception) {
            val fallbackSample = (maxOf(options.outWidth, options.outHeight) / 1024).coerceAtLeast(1)
            BitmapFactory.decodeFile(imageFile.absolutePath, BitmapFactory.Options().apply {
                inSampleSize = fallbackSample
                inPreferredConfig = Bitmap.Config.ARGB_8888
            })
        } ?: return null
        val square = if (crop.width == crop.height) crop else {
            val cropSide = minOf(crop.width, crop.height)
            Bitmap.createBitmap(crop, (crop.width - cropSide) / 2, (crop.height - cropSide) / 2, cropSide, cropSide)
        }
        val orientation = try { ExifInterface(imageFile.absolutePath).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL) } catch (_: Exception) { ExifInterface.ORIENTATION_NORMAL }
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.setScale(-1f, 1f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.setScale(1f, -1f)
        }
        val oriented = if (!matrix.isIdentity) Bitmap.createBitmap(square, 0, 0, square.width, square.height, matrix, true) else square
        val input = if (oriented.width != 224 || oriented.height != 224) Bitmap.createScaledBitmap(oriented, 224, 224, true) else oriented
        val pixels = IntArray(224 * 224)
        input.getPixels(pixels, 0, 224, 0, 0, 224, 224)
        val tensorData = ByteBuffer.allocateDirect(224 * 224 * 3).order(ByteOrder.nativeOrder())
        pixels.forEach { pixel ->
            tensorData.put(((pixel shr 16) and 0xff).toByte())
            tensorData.put(((pixel shr 8) and 0xff).toByte())
            tensorData.put((pixel and 0xff).toByte())
        }
        tensorData.rewind()
        val guess = OnnxTensor.createTensor(environment, tensorData, longArrayOf(1, 224, 224, 3), OnnxJavaType.UINT8).use { tensor ->
            session.run(mapOf(inputName to tensor)).use { results ->
                val output = results[0] as OnnxTensor
                var bestIndex = 0
                var bestConfidence = Float.NEGATIVE_INFINITY
                val floatScores = output.floatBuffer
                if (floatScores != null && floatScores.capacity() >= 1000) {
                    for (index in 0 until 1000) {
                        val score = floatScores.get(index)
                        if (score > bestConfidence) { bestIndex = index; bestConfidence = score }
                    }
                } else {
                    val byteScores = output.byteBuffer
                    require(byteScores.capacity() >= 1000) { "The image model returned fewer than 1,000 labels." }
                    var bestByte = -1
                    for (index in 0 until 1000) {
                        val score = byteScores.get(index).toInt() and 0xff
                        if (score > bestByte) { bestIndex = index; bestByte = score }
                    }
                    bestConfidence = bestByte / 255f
                }
                VisualGuess(labels[bestIndex], topicFor(bestIndex, labels[bestIndex]), bestConfidence)
            }
        }
        if (input !== crop) input.recycle()
        if (oriented !== square) oriented.recycle()
        if (square !== crop) square.recycle()
        crop.recycle()
        return guess
        } finally {
            imageFile.delete()
        }
    }

    override fun close() = session.close()
}

private fun topicFor(index: Int, label: String): String? {
    if (index in 281..285) return "Cats"
    if (index in 151..268) return "Dogs"
    if (index in 7..24 || index in 80..146) return "Birds"
    if (index in 0..397) return "Animals"
    val text = label.lowercase(Locale.ROOT).replace('-', ' ')
    val words = text.split(Regex("[^a-z]+"))
    val groups = mapOf(
        "Food" to setOf("bagel", "banana", "bread", "broccoli", "burrito", "cake", "candy", "carrot", "chocolate", "coffee", "cookie", "corn", "donut", "fruit", "hamburger", "hot dog", "ice cream", "lemon", "lime", "meat", "mushroom", "orange", "pasta", "pizza", "salad", "sandwich", "soup", "strawberry", "sushi", "taco", "tomato", "vegetable", "waffle"),
        "Vehicles" to setOf("aircraft", "airliner", "ambulance", "bicycle", "boat", "bus", "car", "convertible", "jeep", "limousine", "locomotive", "motorcycle", "ship", "scooter", "taxi", "tractor", "train", "truck", "van"),
        "Nature" to setOf("beach", "cliff", "cloud", "desert", "field", "flower", "forest", "garden", "glacier", "grass", "hill", "island", "lake", "landscape", "mountain", "ocean", "plant", "river", "sea", "shore", "sky", "tree", "valley", "volcano", "waterfall"),
        "Sports" to setOf("ball", "baseball", "basketball", "golf", "hockey", "racket", "rugby", "skateboard", "ski", "snowboard", "soccer", "surfboard", "tennis", "volleyball"),
    )
    return groups.entries.firstOrNull { (_, terms) -> terms.any { term ->
        if (' ' in term) text.contains(term) else term in words
    } }?.key
}
